import requests
import json
import sys
from pathlib import Path
import config.setting as setting
from typing import Dict, Any
import argparse

def load_intent_config(intent_name, config_path=None):
    if config_path is None:
        config_path = setting.INTENT_CONFIG
    with open(config_path, "r", encoding="utf-8") as f:
        intents = json.load(f)
    return intents.get(intent_name, None)

def get_arg_value(arg_name, user_input_dict):
    return user_input_dict.get(arg_name, "")

def call_server(tool, args):
    url_map = {
        "batch_anomaly": setting.BATCH_ANOMALY_URL,
        "spc_summary": setting.SPC_SUMMARY_URL,
        "production_summary": setting.PRODUCTION_SUMMARY_URL,
        "downtime_summary": setting.DOWNTIME_SUMMARY_URL,
        "yield_summary": setting.YIELD_SUMMARY_URL,
        "anomaly_trend": setting.ANOMALY_TREND_URL,
        "KPI_summary": setting.KPI_SUMMARY_URL,
        "issue_tracker": setting.ISSUE_TRACKER_URL
    }
    url = url_map.get(tool)
    if not url:
        return {"status": "ERROR", "data": f"Tool {tool} not supported"}
    payload = {
        "trace_id": f"trace-{tool}",
        "tool": tool,
        "args": args
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"status": "ERROR", "data": str(e)}

def summarize_tool_result(tool, tool_result):
    # 根據不同 tool 彈性摘要
    if tool_result.get("status") != "OK":
        return f"【無資料/異常: {tool_result.get('data','')}】"
    # 針對不同 tool 可自訂重點
    if tool == "batch_anomaly":
        data = tool_result.get("data", [{}])[0]
        return f"異常數: {data.get('abnormal_count', 0)}, 特徵: {data.get('abnormal_features', [])}"
    elif tool == "spc_summary":
        data = tool_result.get("data", [{}])[0]
        return f"SPC異常數: {data.get('abnormal_count', 0)}, SPC異常: {data.get('abnormal_spc', [])}"
    # 其他工具可依需求擴充
    return json.dumps(tool_result.get("data"), ensure_ascii=False)

def summarize_batch_context(batch_id, tool_results: Dict[str, str]):
    # 彙整單一批次所有 tool 的重點
    summary = f"批次「{batch_id}」：\n"
    for tool, summary_text in tool_results.items():
        summary += f"{tool}摘要：{summary_text}\n"
    return summary

def call_llm(prompt, system_msg, api_key=None, model="gpt-4"):
    import openai
    api_key = api_key or setting.OPENAI_API_KEY
    client = openai.OpenAI(api_key=api_key)
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": prompt}
    ]
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.2
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[LLM呼叫失敗] {str(e)}"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", help="批次ID，多個用逗號分隔。不指定則自動抓全部。")
    parser.add_argument("--intent", default="查詢批次異常", help="意圖名稱")
    args = parser.parse_args()

    # 取得所有批次ID
    if args.batch:
        batch_ids = [x.strip().zfill(2) for x in args.batch.split(",") if x.strip()]
    else:
        cache_dir = Path(setting.JSON_CACHE)
        batch_ids = [f.stem for f in cache_dir.glob("*.json")]
        batch_ids.sort()

    intent = load_intent_config(args.intent)
    if not intent:
        print(f"[錯誤] 找不到 intent: {args.intent}")
        exit(1)

    all_batch_summaries = []
    for batch_id in batch_ids:
        user_input_dict = {"batch_id": batch_id}
        tool_results = {}
        for call in intent["tool_calls"]:
            tool = call["tool"]
            args_dict = {arg: get_arg_value(arg, user_input_dict) for arg in call["args"]}
            tool_result = call_server(tool, args_dict)
            tool_results[tool] = summarize_tool_result(tool, tool_result)
        # 彙整單一批次所有 tool 的重點
        all_batch_summaries.append(summarize_batch_context(batch_id, tool_results))

    # 組合所有批次的重點摘要
    prompt = "下方為多個批次的重點摘要：\n"
    for batch_summary in all_batch_summaries:
        prompt += batch_summary
    prompt += "\n請依據上述所有批次資訊，歸納各批次的品質問題、是否需現場改善，並提出總體檢討/改善建議。"

    system_msg = intent.get("system_message", "你是產線專家，請根據資料產生專業建議。")
    print("=== 傳送給 LLM 的 prompt ===\n", prompt)
    llm_reply = call_llm(prompt, system_msg)
    print("=== LLM 回覆 ===\n", llm_reply)
