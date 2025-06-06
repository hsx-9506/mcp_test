import os
import math
import json
import re
import math
import config.setting as setting
from pathlib import Path
import pandas as pd
import argparse
from datetime import datetime
import time

# 讀取設定
DEFAULT_SRC = setting.DATA_SRC
DEFAULT_DST = setting.JSON_CACHE

def safe_str(x):
    if pd.isna(x):
        return None
    s = str(x).strip()
    if s.lower() == "nan" or not s:
        return None
    return s

def nan_to_none(obj):
    if isinstance(obj, float) and math.isnan(obj):
        return None
    elif isinstance(obj, dict):
        return {k: nan_to_none(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [nan_to_none(v) for v in obj]
    else:
        return obj

def extract_tail_number(filename):
    match = re.search(r'(\d+)(?!.*\d)', filename)
    return match.group(1) if match else filename

def is_number(x):
    try:
        float(x)
        return True
    except Exception:
        return False

def nowstr():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z")

def calc_cpk_ppk(measurements, usl, lsl):
    vals = [x["value"] for x in measurements if is_number(x["value"])]
    if len(vals) < 2 or usl is None or lsl is None:
        return None, None
    mean = sum(vals) / len(vals)
    std = math.sqrt(sum((v-mean)**2 for v in vals) / (len(vals)-1))
    if std == 0:
        return None, None
    cpk = min((usl-mean)/(3*std), (mean-lsl)/(3*std))
    ppk = cpk  # 假設只計算一次樣本，與 Cpk 相同（如要嚴謹請補上群內與總體標準差）
    return round(cpk, 4), round(ppk, 4)

def etl_inspection_excel(excel_path: Path):
    df = pd.read_excel(excel_path, header=None, engine="openpyxl")
    # === meta資料 ===
    vendor = safe_str(df.iloc[0, 6]) if df.shape[0] > 0 and df.shape[1] > 6 else None
    batch_id_in_file = safe_str(df.iloc[1, 6]) if df.shape[0] > 1 and df.shape[1] > 6 else None
    machine_id_in_file = safe_str(df.iloc[2, 6]) if df.shape[0] > 2 and df.shape[1] > 6 else None
    product_name = safe_str(df.iloc[3, 6]) if df.shape[0] > 3 and df.shape[1] > 6 else None
    part_no = safe_str(df.iloc[4, 6]) if df.shape[0] > 4 and df.shape[1] > 6 else None

    # 找所有特性分頁（跳過Summary）
    xl = pd.ExcelFile(excel_path)
    features = []
    for sheet in xl.sheet_names:
        if sheet.lower() == "summary":
            continue
        body = xl.parse(sheet)
        # 取得欄位位置
        try:
            name = str(body.iloc[0, 0])
            spec = float(body.iloc[0, 1])
            usl = float(body.iloc[1, 1])
            lsl = float(body.iloc[2, 1])
            unit = str(body.iloc[0, 3])
            sample_size = int(body.iloc[2, 2]) if is_number(body.iloc[2, 2]) else None
        except Exception:
            continue
        # 抓所有量測數值
        measurements = []
        abnormal_detail = []
        last_timestamp = None  # 新增：記錄上一次的時間

        for i, row in body.iterrows():
            if not is_number(row.iloc[0]):
                continue
            seq = int(row.iloc[0])
            value = float(row.iloc[1]) if is_number(row.iloc[1]) and not pd.isna(row.iloc[1]) else None
            if value is None:
                continue  # 直接跳過這筆沒有數值的量測資料

            # 處理timestamp欄，支援自動補上前一個時段
            raw_time = row.iloc[2] if row.shape[0] > 2 else None
            if pd.notna(raw_time) and str(raw_time).strip():
                timestamp = str(raw_time)
                last_timestamp = timestamp  # 更新目前的時段
            else:
                timestamp = last_timestamp  # 補上前一個時段

            out_of_spec = False
            if value > usl or value < lsl:
                out_of_spec = True
                abnormal_detail.append(f"第{seq}筆量測值{'超上限' if value > usl else '超下限'}")
            measurements.append({
                "seq": seq, "value": value, "timestamp": timestamp, "out_of_spec": out_of_spec
            })

        cpk, ppk = calc_cpk_ppk(measurements, usl, lsl)
        cpk_alert = cpk is not None and cpk < 1.33
        ppk_alert = ppk is not None and ppk < 1.33
        features.append({
            "feature_name": name,
            "spec": spec,
            "usl": usl,
            "lsl": lsl,
            "unit": unit,
            "sample_size": sample_size,
            "measurements": measurements,
            "cpk": cpk,
            "ppk": ppk,
            "cpk_alert": cpk_alert,
            "cpk_reason": "Cpk低於1.33" if cpk_alert else "",
            "ppk_alert": ppk_alert,
            "ppk_reason": "Ppk低於1.33" if ppk_alert else "",
            "abnormal_detail": abnormal_detail
        })

    return {
        "meta": {
            "machine_id": extract_tail_number(excel_path.stem),
            "batch_id": f"{batch_id_in_file}_{extract_tail_number(excel_path.stem)}",
            "source_file": os.path.basename(excel_path),
            "etl_time": nowstr()
        },
        "summary": {
            "part_no": part_no,
            "product_name": product_name,
            "vendor": vendor
        },
        "features": features,
        "etl_log": {"status": "success", "msg": ""}
    }

def batch_etl(src_dir, dst_dir):
    src = Path(src_dir)
    dst = Path(dst_dir)
    dst.mkdir(parents=True, exist_ok=True)
    files = list(src.glob("*.xlsx"))
    print(f"共偵測到 {len(files)} 筆 Excel 檔案，開始ETL...")
    for file in files:
        try:
            result = etl_inspection_excel(file)
            out_path = dst / f"{result['meta']['machine_id']}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(nan_to_none(result), f, ensure_ascii=False, indent=2)
            print(f"檔案 {file.name} → {out_path.name} 產生成功")
        except Exception as e:
            print(f"處理 {file.name} 失敗: {e}")

def watch_etl(src_dir, dst_dir, interval=300):
    src = Path(src_dir)
    dst = Path(dst_dir)
    dst.mkdir(parents=True, exist_ok=True)
    已處理 = set(f.stem for f in dst.glob("*.json"))
    print(f"進入監控模式，每 {interval} 秒自動同步 Excel → JSON")
    while True:
        filelist = list(src.glob("*.xlsx"))
        新檔案 = [f for f in filelist if f.stem not in 已處理]
        if 新檔案:
            print(f"偵測到 {len(新檔案)} 筆新檔案，執行ETL...")
        for file in 新檔案:
            try:
                result = etl_inspection_excel(file)
                out_path = dst / f"{result['meta']['machine_id']}.json"
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(nan_to_none(result), f, ensure_ascii=False, indent=2)
                print(f"檔案 {file.name} → {out_path.name} 產生成功")
                已處理.add(file.stem)
            except Exception as e:
                print(f"處理 {file.name} 失敗: {e}")
        time.sleep(interval)

def main():
    parser = argparse.ArgumentParser(description="最嚴謹ETL Excel→JSON for MCP")
    parser.add_argument("--src", type=str, default=DEFAULT_SRC, help="來源 Excel 資料夾")
    parser.add_argument("--dst", type=str, default=DEFAULT_DST, help="輸出 JSON 快取資料夾")
    parser.add_argument("--watch", action="store_true", help="持續監控模式")
    parser.add_argument("--interval", type=int, default=300, help="監控間隔秒數 (預設300秒)")
    args = parser.parse_args()
    if args.watch:
        watch_etl(args.src, args.dst, args.interval)
    else:
        batch_etl(args.src, args.dst)

if __name__ == "__main__":
    main()
