#!/usr/bin/env python3
"""
yield_summary_server.py

自動彙整指定日期的良率資料，回傳所有產品/產線/班別的良率統計與異常批次。
標準 API 回傳格式，支援 LLM 多工具自動化查詢。

啟動方式：
  uvicorn mcp_server.yield_summary_server:app --host 0.0.0.0 --port 8005
"""

import config.setting as setting
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uuid

# 設定資料來源資料夾
DATA_DIR = Path(setting.MOCK_YIELD_SUMMARY)

# MCP Tool Schema & Pydantic 模型
class ToolCall(BaseModel):
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool: str
    args: Dict[str, Any]

# 定義 API 回傳格式
class ToolResult(BaseModel):
    trace_id: str
    status: str
    data: List[Dict[str, Any]]

# 建立 FastAPI 伺服器
app = FastAPI(title="Yield Summary MCP-server")

# 將字串轉為 datetime 物件
@app.post("/tool_call", response_model=ToolResult)
def handle_tool_call(req: ToolCall):
    if req.tool != "yield_summary":
        raise HTTPException(400, "Unsupported tool")
    date = req.args.get("date")
    if not date:
        raise HTTPException(400, "date required")

    csv_path = DATA_DIR / f"{date}.csv"
    if not csv_path.exists():
        raise HTTPException(404, f"No yield data for {date}")

    try:
        df = pd.read_csv(csv_path, encoding="utf-8")
    except Exception as e:
        raise HTTPException(500, f"Failed to read yield data: {e}")

    records = df.to_dict(orient="records")
    return ToolResult(
        trace_id=req.trace_id,
        status="OK",
        data=records
    )

# 啟動 FastAPI 伺服器
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
