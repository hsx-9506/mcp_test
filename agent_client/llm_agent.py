import openai
import config.setting as setting
import requests
import argparse
import uuid
import logging
import json
from pathlib import Path

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

# 新版 openai 套件需這樣初始化
client = openai.OpenAI(api_key=setting.OPENAI_API_KEY)

def summarize_context(context):
    # 彙整單一批次重點
    batch_id = context["batch_id"]
    anomaly = context["batch_anomaly"]
    spc = context["spc_summary"]

    summary = f"批次「{batch_id}」："
    # 異常摘要
    if anomaly.get("has_abnormal"):
        summary += f"\n  - 有異常特徵 {anomaly.get('abnormal_count', 0)} 項："
        for feat in anomaly.get("abnormal_features", []):
            summary += f"\n    * {feat.get('feature_name', '')}，異常細節：{feat.get('abnormal_detail', '')}"
    else:
        summary += "\n  - 無異常特徵"

    # SPC 異常
    if spc.get("has_abnormal_spc"):
        summary += f"\n  - SPC 異常 {spc.get('abnormal_count', 0)} 項："
        for item in spc.get("abnormal_spc", []):
            summary += f"\n    * {item.get('feature_name', '')}，cpk={item.get('cpk')}, ppk={item.get('ppk')}"
    else:
        summary += "\n  - SPC 製程能力皆正常"

    return summary

def main():
    parser = argparse.ArgumentParser(description="LLM agent 多工具 MCP 呼叫（setting.py 統一版）")
    parser.add_argument("--batch", help="目標批次ID (多個逗號分隔)，不指定則自動處理全部")
    args = parser.parse_args()

    if args.batch:
        batch_ids = [x.strip().zfill(2) for x in args.batch.split(",") if x.strip()]
    else:
        # 自動讀取所有 json_cache 下的批次
        cache_dir = Path(setting.DATA_CACHE)
        batch_ids = [f.stem for f in cache_dir.glob("*.json")]
        batch_ids.sort()  # 依檔名排序

    all_context = []
    for batch_id in batch_ids:
        print(f"\n=== 處理批次：{batch_id} ===")
        anomaly_result = call_mcp_server(setting.BATCH_ANOMALY_URL, "batch_anomaly", batch_id)
        spc_result = call_mcp_server(setting.SPC_SUMMARY_URL, "spc_summary", batch_id)
        context = {
            "batch_id": batch_id,
            "batch_anomaly": anomaly_result["data"][0] if anomaly_result.get("data") else {},
            "spc_summary": spc_result["data"][0] if spc_result.get("data") else {}
        }
        if context["batch_anomaly"].get("error") or context["spc_summary"].get("error"):
            print(f"[警告] 批次 {batch_id} 的 MCP 回應異常：")
            print(json.dumps(context, ensure_ascii=False, indent=2))
            continue
        all_context.append(context)

    if not all_context:
        print("所有批次皆無法取得有效資料，結束。")
        return

    # 組合多批次的 prompt（只彙整重點）
    prompt = "下方為多個批次的檢驗異常與SPC重點摘要：\n"
    for ctx in all_context:
        prompt += summarize_context(ctx) + "\n"
    prompt += "\n請依據上述所有批次資訊，歸納各批次的品質問題、是否需現場改善，並提出總體檢討/改善建議。"

    print("\n===== 傳送給 LLM 的 prompt =====\n")
    print(prompt)
    print("\n===== LLM 回覆 =====\n")
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "你是製造現場的品質管理專家。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        answer = response.choices[0].message.content.strip()
        print(answer)
    except Exception as e:
        print(f"[OpenAI 呼叫失敗] {e}")

if __name__ == "__main__":
    main()
