#!/usr/bin/env python3
"""
llm_agent.py

模擬 LLM agent：收到用戶提問（如查詢特定批次異常/製程狀態），
語意拆解成多個 tool_call，分別呼叫 batch_anomaly、spc_summary 等 MCP-server，
將所有結果彙整後，組 prompt 並用 OpenAI LLM 回答。

用法：
    python llm_agent.py --batch <批次關鍵字>
"""

import os
import json
import uuid
import requests
import argparse

import openai

# MCP-server 服務端點
BATCH_ANOMALY_URL = "http://127.0.0.1:8001/tool_call"
SPC_SUMMARY_URL   = "http://127.0.0.1:8002/tool_call"

def call_mcp_server(url, tool, batch_id):
    """發送 tool_call 到 MCP-server，回傳資料"""
    payload = {
        "trace_id": str(uuid.uuid4()),
        "tool": tool,
        "args": {"batch_id": batch_id}
    }
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    return resp.json()

def main():
    parser = argparse.ArgumentParser(description="LLM agent 多工具 MCP 呼叫")
    parser.add_argument("--batch", required=True, help="目標批次ID (json_cache檔名關鍵字)")
    args = parser.parse_args()
    batch_id = args.batch

    # === 語意拆解子任務（模擬 LLM 拆解）===
    print(f"[LLM agent] 目標批次：{batch_id}")
    print("1. 呼叫 batch_anomaly_server...")
    anomaly_result = call_mcp_server(BATCH_ANOMALY_URL, "batch_anomaly", batch_id)

    print("2. 呼叫 spc_summary_server...")
    spc_result = call_mcp_server(SPC_SUMMARY_URL, "spc_summary", batch_id)

    # === 彙整所有 MCP 回覆 ===
    prompt_context = {
        "batch_anomaly": anomaly_result["data"][0],
        "spc_summary": spc_result["data"][0]
    }

    # 組成 prompt
    prompt = (
        f"下方提供批次「{batch_id}」的檢驗異常統計與SPC summary資訊：\n"
        f"---\n"
        f"異常摘要：\n{json.dumps(prompt_context['batch_anomaly'], ensure_ascii=False, indent=2)}\n"
        f"---\n"
        f"SPC 製程能力分析：\n{json.dumps(prompt_context['spc_summary'], ensure_ascii=False, indent=2)}\n"
        f"---\n"
        f"請依據上述資訊，判斷該批次最可能的品質問題、是否需現場改善、以及建議的檢討/改善方向。"
    )

    # === 呼叫 LLM（OpenAI GPT-4）===
    openai.api_key = os.getenv("OPENAI_API_KEY", "")
    if not openai.api_key:
        print("請先設定環境變數 OPENAI_API_KEY")
        return

    print("\n===== 傳送給 LLM 的 prompt =====\n")
    print(prompt)
    print("\n===== LLM 回覆 =====\n")

    resp = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "你是製造現場的品質管理專家。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    answer = resp.choices[0].message.content.strip()
    print(answer)

if __name__ == "__main__":
    main()
