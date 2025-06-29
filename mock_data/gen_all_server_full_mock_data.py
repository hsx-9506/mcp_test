"""
gen_all_server_full_mock_data.py

自動產生結構化且具因果邏輯的製造資料（正常／異常皆有），可供 LLM 訓練測試用。
異常批次會因主因（如原料異常、設備故障、人員誤操作等）同時出現多項指標異常。
"""

import json
import random
from datetime import datetime, timedelta

NUM_NORMAL = 15
NUM_ABNORMAL = 3

# 正常批次產生器
def gen_normal_batch(idx):
    base_date = datetime(2025, 6, 18)
    batch_id = f"B{1000+idx:04d}"
    product = random.choice(["P1", "P2", "P3"])
    machine_id = random.choice(["M01", "M02", "M03"])
    date = (base_date + timedelta(days=idx)).strftime("%Y-%m-%d")
    good_qty = random.randint(950, 1000)
    ng_qty = random.randint(0, 10)
    actual_qty = good_qty + ng_qty
    return {
        "batch_id": batch_id,
        "machine_id": machine_id,
        "line": "A",
        "shift": "早班",
        "product": product,
        "date": date,
        "target_qty": 1000,
        "actual_qty": actual_qty,
        "achieve_rate": round(100 * actual_qty / 1000, 1),
        "event_count": 0,
        "total_minutes": 0,
        "main_reason": "",
        "remark": "",
        "good_qty": good_qty,
        "ng_qty": ng_qty,
        "yield_percent": round(100 * good_qty / actual_qty, 2),
        "event_type": "",
        "abnormal_code": "",
        "count": 0,
        "anomaly_remark": "",
        "kpi_name": "良率",
        "value": round(100 * good_qty / actual_qty, 2),
        "target": 98,
        "kpi_achieve_rate": round(100 * good_qty / actual_qty, 2),
        "issue_id": "",
        "status": "closed",
        "owner": "",
        "created_at": date,
        "closed_at": date,
        "description": "",
        "abnormal_count": 0,
        "abnormal_features": [],
        "total_spc_items": 1,
        "spc_items": [{
            "feature_name": "規格標準",
            "spec": 0.2395,
            "usl": 0.243,
            "lsl": 0.236,
            "unit": "inch",
            "sample_size": 5,
            "measurements": [
                {"seq": i+1, "value": round(random.uniform(0.237, 0.242), 4), "timestamp": date, "out_of_spec": False}
                for i in range(5)
            ],
            "cpk": round(random.uniform(1.3, 1.8), 2),
            "ppk": round(random.uniform(1.3, 1.8), 2),
            "cpk_alert": False,
            "cpk_reason": "",
            "ppk_alert": False,
            "ppk_reason": "",
            "abnormal_detail": []
        }]
    }

# 有邏輯的異常批次（例：原料異常，導致NG高、良率低、CPK/PPK低、SPC異常）
def gen_abnormal_batch(idx, reason_type):
    base_date = datetime(2025, 6, 18)
    batch_id = f"X{9000+idx:04d}"
    product = "P2"
    machine_id = "M03"
    date = (base_date + timedelta(days=idx)).strftime("%Y-%m-%d")
    # 設定異常主因
    if reason_type == "原料異常":
        main_reason = "原料異常"
        remark = "原料規格不符導致多項尺寸超規"
        ng_qty = 100
        good_qty = 800
        cpk = 0.85
        ppk = 0.80
        spc_measurements = [
            {"seq": 1, "value": 0.245, "timestamp": date, "out_of_spec": True},
            {"seq": 2, "value": 0.246, "timestamp": date, "out_of_spec": True},
            {"seq": 3, "value": 0.239, "timestamp": date, "out_of_spec": False},
            {"seq": 4, "value": 0.241, "timestamp": date, "out_of_spec": False},
            {"seq": 5, "value": 0.246, "timestamp": date, "out_of_spec": True}
        ]
        cpk_alert = True
        ppk_alert = True
        abnormal_detail = [0.245, 0.246, 0.246]
    elif reason_type == "設備故障":
        main_reason = "設備異常"
        remark = "設備震動導致良率下滑"
        ng_qty = 60
        good_qty = 870
        cpk = 1.00
        ppk = 0.95
        spc_measurements = [
            {"seq": 1, "value": 0.235, "timestamp": date, "out_of_spec": True},
            {"seq": 2, "value": 0.237, "timestamp": date, "out_of_spec": False},
            {"seq": 3, "value": 0.236, "timestamp": date, "out_of_spec": True},
            {"seq": 4, "value": 0.238, "timestamp": date, "out_of_spec": False},
            {"seq": 5, "value": 0.239, "timestamp": date, "out_of_spec": False}
        ]
        cpk_alert = True
        ppk_alert = True
        abnormal_detail = [0.235, 0.236]
    else:
        main_reason = "人員誤操作"
        remark = "操作失誤造成規格偏移"
        ng_qty = 40
        good_qty = 920
        cpk = 0.92
        ppk = 0.90
        spc_measurements = [
            {"seq": 1, "value": 0.236, "timestamp": date, "out_of_spec": True},
            {"seq": 2, "value": 0.237, "timestamp": date, "out_of_spec": False},
            {"seq": 3, "value": 0.240, "timestamp": date, "out_of_spec": False},
            {"seq": 4, "value": 0.243, "timestamp": date, "out_of_spec": True},
            {"seq": 5, "value": 0.241, "timestamp": date, "out_of_spec": False}
        ]
        cpk_alert = True
        ppk_alert = True
        abnormal_detail = [0.236, 0.243]

    actual_qty = good_qty + ng_qty
    return {
        "batch_id": batch_id,
        "machine_id": machine_id,
        "line": "B",
        "shift": "夜班",
        "product": product,
        "date": date,
        "target_qty": 1000,
        "actual_qty": actual_qty,
        "achieve_rate": round(100 * actual_qty / 1000, 1),
        "event_count": 2,
        "total_minutes": 35,
        "main_reason": main_reason,
        "remark": remark,
        "good_qty": good_qty,
        "ng_qty": ng_qty,
        "yield_percent": round(100 * good_qty / actual_qty, 2),
        "event_type": "異常停機",
        "abnormal_code": "E99",
        "count": 1,
        "anomaly_remark": remark,
        "kpi_name": "良率",
        "value": round(100 * good_qty / actual_qty, 2),
        "target": 98,
        "kpi_achieve_rate": round(100 * good_qty / actual_qty, 2),
        "issue_id": f"ISSUE{batch_id[-4:]}",
        "status": "open",
        "owner": "王小明",
        "created_at": date,
        "closed_at": "",
        "description": remark,
        "abnormal_count": 1,
        "abnormal_features": [{
            "feature_name": "規格標準",
            "cpk": cpk,
            "cpk_alert": cpk_alert,
            "cpk_reason": f"Cpk過低 ({main_reason})" if cpk_alert else "",
            "ppk": ppk,
            "ppk_alert": ppk_alert,
            "ppk_reason": f"Ppk過低 ({main_reason})" if ppk_alert else "",
            "abnormal_detail": abnormal_detail
        }],
        "total_spc_items": 1,
        "spc_items": [{
            "feature_name": "規格標準",
            "spec": 0.2395,
            "usl": 0.243,
            "lsl": 0.236,
            "unit": "inch",
            "sample_size": 5,
            "measurements": spc_measurements,
            "cpk": cpk,
            "ppk": ppk,
            "cpk_alert": cpk_alert,
            "cpk_reason": f"Cpk過低 ({main_reason})" if cpk_alert else "",
            "ppk_alert": ppk_alert,
            "ppk_reason": f"Ppk過低 ({main_reason})" if ppk_alert else "",
            "abnormal_detail": abnormal_detail
        }]
    }

if __name__ == "__main__":
    random.seed(42)
    data = [gen_normal_batch(i) for i in range(NUM_NORMAL)]
    # 固定三種異常案例
    abnormal_types = ["原料異常", "設備故障", "人員誤操作"]
    for i, t in enumerate(abnormal_types):
        data.append(gen_abnormal_batch(i, t))
    # 輸出
    with open("all_server_full_mock_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Mock data 已產出，包含正常與三種異常案例。")
