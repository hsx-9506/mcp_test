import os, re, json, requests, time, argparse
from openai import OpenAI
from pathlib import Path
from typing import Dict
from collections import Counter
from agent_client.reviewer_agent import review_answer

from agent_client.reviewer_agent import review_answer, generate_suggestion
from config.setting import OPENAI_API_KEY, JSON_CACHE, UNIFIED_SERVER_URL
from config.prompts import (
    SYSTEM_PROMPT, DECOMPOSER_SYSTEM_PROMPT, USER_PROMPT_TEMPLATE,
    load_intents, build_llm_intent_doc
)

INTENTS = load_intents()
LLM_INTENT_DOC = build_llm_intent_doc(INTENTS)

# ────────────── 語意拆解與自動 tool_call ──────────────
def extract_json(text: str) -> str:
    """
    從 LLM 回覆中擷取 JSON 區塊，若無則回傳原文
    """
    match = re.search(r"```(?:json)?\s*({[\s\S]*?})\s*```", text)
    if match:
        return match.group(1)
    return text

def parse_intent(user_query: str, intents=INTENTS):
    user_query_lc = user_query.lower()
    for intent in intents:
        if any(kw in user_query_lc for kw in intent.get("keywords", [])):
            return intent
    for intent in intents:
        if intent.get("intent") == "other":
            return intent
    return None

def decompose_query(user_input: str) -> dict:
    """
    LLM 拆解語意，依 DECOMPOSER_SYSTEM_PROMPT/USER_PROMPT_TEMPLATE 要求，產生 intent/flags/tool_calls 結構
    """
    user_prompt = USER_PROMPT_TEMPLATE.format(user_input=user_input)
    messages = [
        # 明確使用 DECOMPOSER_SYSTEM_PROMPT
        {"role": "system", "content": DECOMPOSER_SYSTEM_PROMPT},
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
def call_server(tool, args, retry=2):
    for attempt in range(retry):
        try:
            resp = requests.get(UNIFIED_SERVER_URL, params={"type": tool, **args}, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            if attempt < retry-1:
                time.sleep(1)
                continue
            else:
                return {"status": "ERROR", "data": str(e)}

# ──────────────────────────────────────
# 彈性摘要各種 tool 的回傳結果（全 tool 支援）
def summarize_tool_result(tool, tool_result):
    status = tool_result.get("status", "").lower()
    data = tool_result.get("data", [])

    # 直接使用工具名稱作為標題，並加上換行
    title = f"{tool}\n"

    # === 異常總覽：條列化每個批次 ===
    if tool == "batch_anomaly":
        if not data:
            return title + "無符合條件的異常批次。"
        content = []
        for item in data:
            if item.get("abnormal_count", 0) > 0 or item.get("abnormal_features"):
                lines = [
                    f"- 批次ID：{item.get('batch_id', 'N/A')}",
                    f"  產品：{item.get('product', 'N/A')}",
                    f"  異常主因：{item.get('main_reason') or item.get('anomaly_remark') or '未標註'}",
                ]
                for f in item.get("abnormal_features", []):
                    lines.append(f"  特性：{f.get('feature_name', '')}")
                    cpk_val = f.get('cpk')
                    ppk_val = f.get('ppk')
                    if isinstance(cpk_val, (int, float)):
                        lines.append(f"    Cpk={cpk_val:.2f} [警告:{f.get('cpk_reason', '')}]")
                    if isinstance(ppk_val, (int, float)):
                        lines.append(f"    Ppk={ppk_val:.2f} [警告:{f.get('ppk_reason', '')}]")
                content.append("\n".join(lines))
        return title + ("\n\n".join(content) if content else "查無異常批次。")

    # === 異常趨勢：條列化每筆異常 ===
    if tool == "anomaly_trend":
        if not data:
            return title + "指定時間範圍內無歷史異常事件可供分析。"
        cause_counts = Counter(item.get('anomaly_remark') for item in data if item.get('anomaly_remark'))
        if not cause_counts:
            return title + "所有歷史異常事件均未標註主因，無法進行趨勢分析。"
        lines = ["主要異常原因分佈："]
        for reason, count in cause_counts.most_common():
            lines.append(f"  - 原因「{reason}」總共發生了 {count} 次。")
        return title + "\n".join(lines)
    
    # === SPC摘要：條列化每個批次的 SPC 狀態 ===
    if tool == "spc_summary":
        if not data:
            return "無 SPC 製程能力資料"
        spc_lines = []
        for item in data:
            for f in item.get("spc_items", []):
                if f.get("cpk_alert") or f.get("ppk_alert"):
                    spc_lines.append(
                        f"批次:{item.get('batch_id','')}, 特性:{f.get('feature_name','')}, Cpk:{f.get('cpk','')}, Ppk:{f.get('ppk','')}, 警告:{f.get('cpk_reason','') or f.get('ppk_reason','')}"
                    )
        if not spc_lines:
            return "所有批次SPC皆正常"
        return "\n".join(spc_lines)
    
    # === 生產摘要：條列化每個批次的生產數據 ===
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

    # === 停機摘要：條列化每個停機事件 ===
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

    # === 品檢紀錄：條列化每個品檢紀錄 ===
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

    # === 品檢單一紀錄：條列化每個品檢項目 ===
    if tool == "anomaly_trend":
        if not data:
            return "本區間無異常趨勢"
        lines = []
        header = "日期\t機台\t產線\t異常類型\t異常代碼\t次數\t備註"
        lines.append(header)
        show = False
        for item in data:
            # 只顯示有異常(次數>0)的紀錄
            count = item.get('count', 0)
            # 部分資料型態可能是字串，要轉成數字
            try:
                count_num = int(count)
            except Exception:
                count_num = 0
            if count_num > 0:
                show = True
                row = "\t".join([
                    str(item.get('date', '')),
                    str(item.get('machine_id', '')),
                    str(item.get('line', '')),
                    str(item.get('event_type', '')),
                    str(item.get('abnormal_code', '')),
                    str(count),
                    str(item.get('anomaly_remark', ''))
                ])
                lines.append(row)
        if not show:
            return "本區間未發現異常趨勢"
        return "\n".join(lines)

    # === KPI摘要：條列化每個KPI紀錄 ===
    if tool == "KPI_summary":
        if not data:
            return "本日無KPI紀錄"
        header = list(data[0].keys())
        table = "\t".join(header) + "\n"
        for row in data:
            table += "\t".join([str(row.get(h, "")) for h in header]) + "\n"
        return table

    # === 問題追蹤：條列化每個工單狀態 ===
    if tool == "issue_tracker":
        if not data:
            return "無未結案工單"
        header = list(data[0].keys())
        table = "\t".join(header) + "\n"
        for row in data:
            table += "\t".join([str(row.get(h, "")) for h in header]) + "\n"
        return table

    if status != "ok":
        return f"【無資料/異常: {tool_result.get('data','')}】"
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

# === 1. 多步查詢 + 容錯 + 上下文 + LLM同步intents ===
def run_agent_smart(user_query, session_history=None, return_summary=False, max_steps=3):
    history = session_history or []
    step_outputs = ["", "", "", "", "", ""]

    # --- 步驟 1: 語意分析 (判斷是否需要使用工具) ---
    decomp_result = None
    try:
        decomp_result = decompose_query(user_query)
        step_outputs[0] = json.dumps(decomp_result, ensure_ascii=False, indent=2)
    except Exception as e:
        step_outputs[0] = f"語意分析失敗: {e}"
        yield 0, step_outputs[0]
        yield "done", (step_outputs, f"抱歉，在分析您的問題時發生錯誤: {e}", "")
        return
        
    yield 0, step_outputs[0]

    # --- 步驟 2: 檢查是否需要呼叫工具 ---
    tool_calls = decomp_result.get("tool_calls", []) if decomp_result else []
    if not tool_calls and decomp_result and decomp_result.get("flags"):
        tool_calls = [{"tool": flag, "args": {}} for flag in decomp_result["flags"]]
    
    if not tool_calls:
        step_outputs[1] = "(不需呼叫工具，進入聊天模式)"
        yield 1, step_outputs[1]
        step_outputs[2] = "(跳過)"
        yield 2, step_outputs[2]
        step_outputs[3] = "(跳過)"
        yield 3, step_outputs[3]
        step_outputs[4] = "(跳過)"
        yield 4, step_outputs[4]
        messages_for_followup = [{"role": "system", "content": SYSTEM_PROMPT}, *history]
        llm_reply = call_llm(messages_for_followup)
        final_suggestion = generate_suggestion(tools_used=set(), user_query=user_query)
        final_response = llm_reply + final_suggestion
        step_outputs[5] = final_response
        yield 5, step_outputs[5]
        yield "done", (step_outputs, final_response, "")
        return

    step_outputs[1] = json.dumps(tool_calls, ensure_ascii=False, indent=2)
    yield 1, step_outputs[1]
    
    # --- 步驟 3: agent tool_call ---
    tool_call_strs = [f"tool: {call.get('tool', '')}, args: {call.get('args', {})}" for call in tool_calls]
    step_outputs[2] = "\n".join(tool_call_strs)
    yield 2, step_outputs[2]

    # --- 步驟 4: server回傳 ---
    tool_results_dict = {}
    tool_result_summaries = []
    for call in tool_calls:
        tool = call.get("tool", "")
        args = call.get("args", {}) or {}
        tool_result = call_server(tool, args, retry=2)
        tool_results_dict[tool] = tool_result
        summary_str = summarize_tool_result(tool, tool_result)
        tool_result_summaries.append(f"【{tool}】\n{summary_str}")
    step_outputs[3] = "\n---\n".join(tool_result_summaries) if tool_result_summaries else "(無server回傳)"
    yield 3, step_outputs[3]
    
    # --- 步驟 5: 組裝摘要 ---
    summary_section = "\n\n".join(tool_result_summaries) # 使用兩個換行符讓摘要之間更清晰
    step_outputs[4] = summary_section if summary_section else "(無摘要)"
    yield 4, step_outputs[4]

    # --- 步驟 6: LLM回覆 ---
    final_user_prompt = (
        f"這是本次查詢的相關資料：\n"
        f"---------------------\n"
        f"【工具查詢結果】\n{summary_section}\n"
        f"---------------------\n\n"
        f"現在，請根據以上資料，並嚴格遵守你的系統指令，回答我最初的問題：\n"
        f"「{user_query}」"
    )

    messages_final = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": final_user_prompt}
    ]

    llm_reply = call_llm(messages_final)
    
    # 【修改點 3】: 呼叫 reviewer_agent 來生成追問建議
    tool_names = {call.get('tool') for call in tool_calls}
    final_suggestion = generate_suggestion(tools_used=tool_names, user_query=user_query)
    
    # 將 LLM 的回覆和 reviewer agent 產生的建議組合起來
    final_response = llm_reply + final_suggestion

    step_outputs[5] = final_response
    yield 5, step_outputs[5]
    yield "done", (step_outputs, final_response, summary_section)

def run_agent(user_query, session_history=None, return_summary=False):
    result = run_agent_smart(user_query, session_history=session_history, return_summary=True)
    if return_summary:
        return result
    else:
        # 這個回傳邏輯可能有問題，但我們先專注於 run_agent_smart
        # 應確保回傳的是最終結果
        final_result = None
        for step_data in result:
            if step_data[0] == 'done':
                final_result = step_data[1]
                break
        return final_result[1] if final_result else ""

# ──────────────────────────────────────
# 呼叫 LLM 生成建議
def call_llm(messages, model="gpt-3.5-turbo", api_key=None, temperature=0.0):
    api_key = api_key or OPENAI_API_KEY
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

    if args.batch:
        batch_ids = [x.strip().zfill(2) for x in args.batch.split(",") if x.strip()]
    else:
        cache_dir = Path(JSON_CACHE)
        batch_ids = [f.stem for f in cache_dir.glob("*.json")]
        batch_ids.sort()

    extra_dict = {}
    if args.extra:
        for item in args.extra:
            if "=" in item:
                k, v = item.split("=", 1)
                extra_dict[k] = v

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
            args_dict = {arg: user_input_dict.get(arg, "") for arg in call.get("args", [])}
            tool_result = call_server(tool, args_dict)
            tool_results[tool] = summarize_tool_result(tool, tool_result)
        all_batch_summaries.append(summarize_batch_context(batch_id, tool_results))

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
    