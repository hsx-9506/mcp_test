import os
import re
import json
import requests
from openai import OpenAI
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any, List
import argparse
import config.setting as setting
from config.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

load_dotenv()
# ────────────── 語意拆解與自動 tool_call ──────────────
def extract_json(text: str) -> str:
    """
    從 LLM 回覆中擷取 JSON 區塊，若無則回傳原文
    """
    match = re.search(r"```(?:json)?\\s*(\\{[\\s\\S]*?\\})\\s*```", text)
    if match:
        return match.group(1)
    return text

def decompose_query(user_input: str) -> dict:
    """
    語意拆解主流程，回傳 LLM 拆解後的 intent/tool_calls 結構
    """
    user_prompt = USER_PROMPT_TEMPLATE.format(user_input=user_input)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]
    response_text = call_llm(messages)
    json_part = extract_json(response_text)
    try:
        result = json.loads(json_part)
    except json.JSONDecodeError:
        raise ValueError("❌ 無法解析 LLM 回應：", response_text)
    return result

# ──────────────────────────────────────
# 統一呼叫 unified_server 查詢
def call_server(tool, args):
    params = {"type": tool}
    params.update(args)
    try:
        resp = requests.get(setting.UNIFIED_SERVER_URL, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"status": "ERROR", "data": str(e)}

# ──────────────────────────────────────
# 彈性摘要各種 tool 的回傳結果（全 tool 支援）
def summarize_tool_result(tool, tool_result):
    if tool_result.get("status") != "OK":
        return f"【無資料/異常: {tool_result.get('data','')}】"
    data = tool_result.get("data", [])

    if tool == "batch_anomaly":
        if not data:
            return "本批次無異常資料"
        item = data[0]
        result = [
            f"批次：{item.get('batch_id', '')}",
            f"產品：{item.get('product_name', '')}",
            f"機台：{item.get('machine_id', '')}",
            f"異常數：{item.get('abnormal_count', 0)}"
        ]
        if item.get("abnormal_features"):
            result.append("異常明細：")
            for f in item["abnormal_features"]:
                desc = f"- 特性：{f.get('feature_name', '')} (Cpk={f.get('cpk', '')})"
                if f.get("cpk_alert"):
                    desc += f" [Cpk警告: {f.get('cpk_reason', '')}]"
                if f.get("ppk_alert"):
                    desc += f" [Ppk警告: {f.get('ppk_reason', '')}]"
                if f.get("abnormal_detail"):
                    desc += f" | 明細: {','.join([str(x) for x in f['abnormal_detail']])}"
                result.append(desc)
        else:
            result.append("本批次無異常特性")
        return "\n".join(result)

    if tool == "spc_summary":
        if not data:
            return "無 SPC 製程能力資料"
        item = data[0]
        lines = [
            f"批次：{item.get('batch_id', '')}",
            f"產品：{item.get('product_name', '')}",
            f"機台：{item.get('machine_id', '')}",
            f"SPC項目數：{item.get('total_spc_items', 0)}",
        ]
        if "spc_items" in item:
            for spc in item["spc_items"]:
                lines.append(f"- 特性：{spc.get('feature_name', '')} | Cpk={spc.get('cpk', '')} | Ppk={spc.get('ppk', '')} | 警告: {'是' if spc.get('cpk_alert') else '否'}")
        else:
            lines.append("無 SPC 明細")
        return "\n".join(lines)

    if tool == "production_summary":
        if not data:
            return "本日無產能資料"
        header = ["機台", "產線", "班別", "目標產量", "實際產量", "達成率(%)"]
        rows = [
            [row.get("machine_id", ""), row.get("line", ""), row.get("shift", ""),
             row.get("target_qty", ""), row.get("actual_qty", ""), row.get("achieve_rate", "")]
            for row in data
        ]
        table = "\t".join(header) + "\n"
        for r in rows:
            table += "\t".join([str(x) for x in r]) + "\n"
        return table

    if tool == "downtime_summary":
        if not data:
            return "本日無停機紀錄"
        header = ["機台", "產線", "班別", "停機次數", "停機總時數(分鐘)", "主因", "備註"]
        rows = [
            [row.get("machine_id", ""), row.get("line", ""), row.get("shift", ""), row.get("event_count", ""),
             row.get("total_minutes", ""), row.get("main_reason", ""), row.get("remark", "")]
            for row in data
        ]
        table = "\t".join(header) + "\n"
        for r in rows:
            table += "\t".join([str(x) for x in r]) + "\n"
        return table

    if tool == "yield_summary":
        if not data:
            return "本日無良率紀錄"
        header = ["產品", "產線", "班別", "良品數", "不良品數", "良率(%)"]
        rows = [
            [row.get("product", ""), row.get("line", ""), row.get("shift", ""),
             row.get("good_qty", ""), row.get("ng_qty", ""), row.get("yield_percent", "")]
            for row in data
        ]
        table = "\t".join(header) + "\n"
        for r in rows:
            table += "\t".join([str(x) for x in r]) + "\n"
        return table

    if tool == "anomaly_trend":
        if not data:
            return "區間內無異常事件"
        header = ["日期", "機台", "產線", "異常類型", "異常代碼", "次數", "備註"]
        rows = [
            [row.get("date",""), row.get("machine_id", ""), row.get("line", ""), row.get("event_type", ""),
             row.get("abnormal_code", ""), row.get("count", ""), row.get("remark", "")]
            for row in data
        ]
        table = "\t".join(header) + "\n"
        for r in rows:
            table += "\t".join([str(x) for x in r]) + "\n"
        return table

    if tool == "KPI_summary":
        if not data:
            return "本日無KPI紀錄"
        header = list(data[0].keys())
        table = "\t".join(header) + "\n"
        for row in data:
            table += "\t".join([str(row.get(h, "")) for h in header]) + "\n"
        return table

    if tool == "issue_tracker":
        if not data:
            return "無未結案工單"
        header = list(data[0].keys())
        table = "\t".join(header) + "\n"
        for row in data:
            table += "\t".join([str(row.get(h, "")) for h in header]) + "\n"
        return table

    # fallback
    return json.dumps(data, ensure_ascii=False, indent=2) if data else "無資料"

# ──────────────────────────────────────
# 彙總批次的各工具摘要
def summarize_batch_context(batch_id, tool_results: Dict[str, str]):
    # 只擷取異常數與SPC警告數等重點
    batch_anomaly = tool_results.get("batch_anomaly", "")
    spc_summary = tool_results.get("spc_summary", "")

    # 擷取異常數
    abnormal_count = 0
    if "異常數：" in batch_anomaly:
        try:
            abnormal_count = int(batch_anomaly.split("異常數：")[1].split("\n")[0])
        except Exception:
            abnormal_count = 0

    # 擷取SPC警告數
    spc_alert_count = 0
    if "警告: 是" in spc_summary:
        spc_alert_count = spc_summary.count("警告: 是")

    summary = (
        f"批次：{batch_id} | 異常數：{abnormal_count} | SPC警告數：{spc_alert_count}\n"
    )
    return summary

# ──────────────────────────────────────
# 主流程：將查詢轉換為 LLM 回覆
def run_agent(query, batch_ids=None, extra_dict=None):
    """
    將主流程包裝成函式，供 UI 或其他程式直接呼叫。
    :param query: 使用者查詢字串
    :param batch_ids: 批次ID list，預設自動抓全部
    :param extra_dict: 其他查詢參數 dict
    :return: LLM 回覆字串
    """
    if batch_ids is None:
        cache_dir = Path(setting.JSON_CACHE)
        batch_ids = [f.stem for f in cache_dir.glob("*.json")]
        batch_ids.sort()
    if extra_dict is None:
        extra_dict = {}
    decomp = decompose_query(query)
    tool_calls = decomp.get("tool_calls", [])
    all_batch_summaries = []
    for batch_id in batch_ids:
        user_input_dict = {"batch_id": batch_id}
        user_input_dict.update(extra_dict)
        tool_results = {}
        for call in tool_calls:
            tool = call["tool"]
            args_dict = {arg: user_input_dict.get(arg, "") for arg in call["args"]}
            tool_result = call_server(tool, args_dict)
            tool_results[tool] = summarize_tool_result(tool, tool_result)
        all_batch_summaries.append(summarize_batch_context(batch_id, tool_results))
    prompt = "下方為多個批次的重點摘要：\n"
    for batch_summary in all_batch_summaries:
        prompt += batch_summary
    prompt += "\n請依據上述所有批次資訊，歸納各批次的品質問題、是否需現場改善，並提出總體檢討/改善建議。"
    prompt += "\n直接用清單與段落條列式回答，不要加任何裝飾用符號。"
    system_msg = "你是產線專家，請根據資料產生專業建議。"
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": prompt}
    ]
    llm_reply = call_llm(messages)
    return llm_reply

# ──────────────────────────────────────
# 呼叫 LLM 生成建議
def call_llm(
    messages: list,
    model: str = "gpt-4o",
    api_key: str = None,
    temperature: float = 0.0
) -> str:
    """
    統一的 OpenAI LLM 呼叫介面
    :param messages: [{"role": "system", "content": ...}, {"role": "user", "content": ...}]
    :param model: 預設 gpt-4o
    :param api_key: 可選，預設用 OPENAI_API_KEY
    :param temperature: 溫度參數
    :return: LLM 回覆文字
    """
    api_key = setting.OPENAI_API_KEY
    client = OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[LLM呼叫失敗] {str(e)}"

# ========= 主要流程 =========
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", help="批次ID，多個用逗號分隔。不指定則自動抓全部。")
    parser.add_argument("--extra", nargs="*", help="其他參數，如 date=2024-05-28")
    parser.add_argument("--decompose", action="store_true", help="僅進行語意分類與 tool_call 拆解")
    args = parser.parse_args()

    if args.decompose:
        query = input("請輸入要分析的問題：")
        result = decompose_query(query)
        print("\n✅ 語意分類：", result.get("intent"))
        print("🧩 tool_calls 拆解：")
        for i, call in enumerate(result.get("tool_calls", []), 1):
            print(f"  {i}. {call}")
        exit(0)

    # 取得所有批次ID
    if args.batch:
        batch_ids = [x.strip().zfill(2) for x in args.batch.split(",") if x.strip()]
    else:
        cache_dir = Path(setting.JSON_CACHE)
        batch_ids = [f.stem for f in cache_dir.glob("*.json")]
        batch_ids.sort()

    # 處理額外參數
    extra_dict = {}
    if args.extra:
        for item in args.extra:
            if "=" in item:
                k, v = item.split("=", 1)
                extra_dict[k] = v

    # 讓使用者輸入自然語言查詢
    query = input("請輸入查詢需求：")
    decomp = decompose_query(query)
    tool_calls = decomp.get("tool_calls", [])
    intent = decomp.get("intent", "")

    all_batch_summaries = []
    for batch_id in batch_ids:
        user_input_dict = {"batch_id": batch_id}
        user_input_dict.update(extra_dict)
        tool_results = {}
        for call in tool_calls:
            tool = call["tool"]
            args_dict = {arg: user_input_dict.get(arg, "") for arg in call["args"]}
            tool_result = call_server(tool, args_dict)
            tool_results[tool] = summarize_tool_result(tool, tool_result)
        all_batch_summaries.append(summarize_batch_context(batch_id, tool_results))

    # 組合所有批次的重點摘要
    prompt = "下方為多個批次的重點摘要：\n"
    for batch_summary in all_batch_summaries:
        prompt += batch_summary
    prompt += "\n請依據上述所有批次資訊，歸納各批次的品質問題、是否需現場改善，並提出總體檢討/改善建議。"

    system_msg = "你是產線專家，請根據資料產生專業建議。"
    print("=== 傳送給 LLM 的 prompt ===\n", prompt)
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": prompt}
    ]
    llm_reply = call_llm(messages)
    print("=== LLM 回覆 ===\n", llm_reply)
