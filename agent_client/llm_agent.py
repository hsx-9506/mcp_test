import openai
import config.setting as setting
import requests
import argparse
import uuid
import logging
import json

def call_mcp_server(url: str, tool: str, batch_id: str) -> dict:
    payload = {
        "trace_id": str(uuid.uuid4()),
        "tool": tool,
        "args": {"batch_id": batch_id}
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        if result.get("status") != "OK" or not result.get("data"):
            raise RuntimeError(f"MCP-server 回傳資料異常: {result}")
        return result
    except Exception as e:
        logging.error(f"呼叫 {tool} 失敗: {e}")
        return {"status": "ERROR", "data": [{"error": str(e)}]}

def main():
    parser = argparse.ArgumentParser(description="LLM agent 多工具 MCP 呼叫（setting.py 統一版）")
    parser.add_argument("--batch", required=True, help="目標批次ID (多個逗號分隔)")
    args = parser.parse_args()
    batch_ids = [x.strip() for x in args.batch.split(",") if x.strip()]

    openai.api_key = setting.OPENAI_API_KEY

    for batch_id in batch_ids:
        print(f"\n=== 處理批次：{batch_id} ===")
        anomaly_result = call_mcp_server(setting.BATCH_ANOMALY_URL, "batch_anomaly", batch_id)
        spc_result = call_mcp_server(setting.SPC_SUMMARY_URL, "spc_summary", batch_id)
        context = {
            "batch_anomaly": anomaly_result["data"][0] if anomaly_result.get("data") else {},
            "spc_summary": spc_result["data"][0] if spc_result.get("data") else {}
        }
        if context["batch_anomaly"].get("error") or context["spc_summary"].get("error"):
            print(f"[警告] 批次 {batch_id} 的 MCP 回應異常：")
            print(json.dumps(context, ensure_ascii=False, indent=2))
            continue
        prompt = (
            f"下方提供批次「{batch_id}」的檢驗異常統計與 SPC summary 資訊：\n"
            f"---\n"
            f"異常摘要：\n{json.dumps(context['batch_anomaly'], ensure_ascii=False, indent=2)}\n"
            f"---\n"
            f"SPC 製程能力分析：\n{json.dumps(context['spc_summary'], ensure_ascii=False, indent=2)}\n"
            f"---\n"
            f"請依據上述資訊，判斷該批次最可能的品質問題、是否需現場改善、以及建議的檢討/改善方向。"
        )
        print("\n===== 傳送給 LLM 的 prompt =====\n")
        print(prompt)
        print("\n===== LLM 回覆 =====\n")
        try:
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
        except Exception as e:
            print(f"[OpenAI 呼叫失敗] {e}")

if __name__ == "__main__":
    main()
