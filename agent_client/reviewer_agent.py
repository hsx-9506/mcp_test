import openai
import os

from config.setting import OPENAI_API_KEY

def review_data(data_json: dict, task_type="data_check") -> dict:
    """
    用 LLM 檢查 MCP-server 回傳的資料內容是否完整、有無明顯缺失或異常。
    回傳建議標註：need_more_info / incomplete 等 flag
    """
    prompt = f"""
你是資料完整性審查專家，請判斷下方 JSON 資料內容是否有明顯缺漏、異常或不合理之處，並回覆如下格式：

- incomplete: True/False
- need_more_info: True/False
- comment: 若有缺失請簡要說明需補哪些欄位或檢查哪些項目
- data_ok: True/False

資料如下：
{data_json}
"""
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "你是生產數據審查員。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        max_tokens=300
    )
    review = resp.choices[0].message.content
    # 解析 review 結果（可用正則/簡單字串判斷）
    result = {
        "incomplete": "True" in review,
        "need_more_info": "True" in review,
        "comment": review
    }
    return result

def review_answer(user_question, mcp_tool_results, llm_reply) -> dict:
    """
    用 LLM 或規則引擎判斷 LLM 回答是否完整、有無回答到重點。
    回傳明確結構 answer_ok: True/False, missing: 條列缺失
    """
    prompt = f"""
你是製造業智能決策審查員，請審查 LLM 回答內容是否已明確解答用戶問題，並根據資料摘要合理分析。
請用下列 JSON 格式回覆：
{{
  "answer_ok": true/false,
  "missing": "若有缺失請條列需補充或需更清楚的點，如無缺失請寫無"
}}

用戶問題：{user_question}
資料摘要：{mcp_tool_results}
模型回答：{llm_reply}
"""
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "你是生產數據審查員。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        max_tokens=300
    )
    review = resp.choices[0].message.content
    # 嘗試解析 json，回退為原有字串比對
    import json as _json
    try:
        review_json = _json.loads(review)
        return {
            "answer_ok": review_json.get("answer_ok", False),
            "missing": review_json.get("missing", review)
        }
    except Exception:
        # fallback: 還是用字串比對
        return {
            "answer_ok": "True" in review,
            "missing": review
        }
