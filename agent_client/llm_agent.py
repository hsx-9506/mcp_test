import requests
import json
import sys
from pathlib import Path
import config.setting as setting
from typing import Dict, Any
import argparse

# ──────────────────────────────────────
# 載入 LLM 回覆模板
def load_intent_config(intent_name, config_path=None):
    if config_path is None:
        config_path = setting.INTENT_CONFIG
    with open(config_path, "r", encoding="utf-8") as f:
        intents = json.load(f)
    return intents.get(intent_name, None)

# ──────────────────────────────────────
# 取得使用者輸入的參數值
def get_arg_value(arg_name, user_input_dict):
    return user_input_dict.get(arg_name, "")

# ──────────────────────────────────────
# 呼叫 MCP server 取得工具結果
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
# 呼叫 LLM 生成建議
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

# ──────────────────────────────────────
# 主程式入口
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", help="批次ID，多個用逗號分隔。不指定則自動抓全部。")
    parser.add_argument("--intent", default="查詢批次異常", help="意圖名稱")
    parser.add_argument("--extra", nargs="*", help="其他參數，如 date=2024-05-28")
    args = parser.parse_args()

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

    # 載入意圖配置
    intent = load_intent_config(args.intent)
    if not intent:
        print(f"[錯誤] 找不到 intent: {args.intent}")
        exit(1)

    # 檢查必要的工具呼叫
    all_batch_summaries = []
    for batch_id in batch_ids:
        user_input_dict = {"batch_id": batch_id}
        user_input_dict.update(extra_dict)
        tool_results = {}
        for call in intent["tool_calls"]:
            tool = call["tool"]
            args_dict = {arg: get_arg_value(arg, user_input_dict) for arg in call["args"]}
            tool_result = call_server(tool, args_dict)
            tool_results[tool] = summarize_tool_result(tool, tool_result)
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
