# prompts.py
SYSTEM_PROMPT = """
You are a semantic agent in a smart manufacturing context. 
Your job is to analyze the user's query, infer the real intention, and map it to **one or more of the following MCP flag types** (see below).
- For every user question, decide which flag(s) (from the list) are needed to answer or accomplish the task.
- If the query involves multiple topics, **return multiple flags** and match each to its subtask.
- Be strict and only return relevant flags. If none fits, reply with "other".
- Output a structured JSON: { "intent": ..., "flags": [ ... ], "subtasks": {flag: [subtask, ...]}, "reasoning": "...", "clarification_needed": false }

### MCP Flags (English=flag, 中文=說明)

production_summary   : 生產數據/進度（批次、產量、進度彙總）
batch_anomaly        : 異常總覽/異常分類（批次異常、異常原因）
anomaly_trend        : 異常趨勢分析（時間序列異常變化）
downtime_summary     : 停機統計（停機時長、停機原因）
spc_summary          : SPC指標/異常（Cpk/Ppk、異常標記、異常明細）
inspection_record    : 品檢單一紀錄（樣本量測結果、規格上下限）
yield_summary        : 良率/報廢率（良品/不良品統計、良率趨勢）
KPI_summary          : 綜合關鍵績效（OEE、稼動率、不良率）
issue_tracker        : 問題追蹤（問題單狀態、回報、追蹤紀錄）

Explain all flag choices in "reasoning". If the user query is ambiguous or lacks info, set "clarification_needed": true.
"""

USER_PROMPT_TEMPLATE = """
【使用者需求】
{user_input}

請根據上述內容：
1. 辨識問題的主要意圖（intent）
2. 推論應對應哪一個或多個 MCP flag（見上表），每個 flag 下請細分一至多個子任務（subtasks）
3. 產生對應的 flags + subtasks 結構化 JSON 回覆（格式見 system prompt）
4. 必須附上選 flag 與任務分解的邏輯解釋（reasoning）

---請直接回覆 JSON  Please output pure JSON only, without any markdown code block.---
"""

import json
from pathlib import Path

def load_intents(path=None):
    """載入intents.json"""
    if path is None:
        # 預設從專案根目錄下 intent_config/intents.json
        path = str(Path(__file__).parent.parent / "intent_config" / "intents.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def build_llm_intent_doc(intents):
    """將intents內容自動產生給LLM看的描述字串"""
    lines = []
    for it in intents:
        line = (
            f"intent: {it['intent']}\n"
            f"tool_call: {', '.join(it['tool_call'])}\n"
            f"keywords: {', '.join(it['keywords'])}\n"
            f"description: {it.get('description','')}\n"
        )
        lines.append(line)
    return "\n".join(lines)

# 載入一次所有intents，供agent同步用
INTENTS = load_intents()
LLM_INTENT_DOC = build_llm_intent_doc(INTENTS)

