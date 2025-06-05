#!/usr/bin/env python3
"""
KPI_summary_server.py

自動彙整指定日期的關鍵績效指標（KPI）資料，回傳各項KPI統計。
標準 API 回傳格式，支援 LLM 多工具自動化查詢。

啟動方式：
  uvicorn mcp_server.KPI_summary_server:app --host 0.0.0.0 --port 8007
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List
import config.setting as setting
import pandas as pd
from pathlib import Path
from datetime import datetime
import uuid

# KPI Summary Server
DATA_DIR = Path(setting.MOCK_KPI_SUMMARY)

# MCP Tool Schema & Pydantic 模型
class ToolCall(BaseModel):
    trace_id: str = str(uuid.uuid4())
    tool: str
    args: Dict[str, Any]

# ToolResult Schema
class ToolResult(BaseModel):
    trace_id: str
    status: str
    data: List[Dict[str, Any]]

# 建立 FastAPI 伺服器
app = FastAPI()

# 將字串轉為 datetime 物件
@app.post("/tool_call", response_model=ToolResult)
def tool_call(payload: ToolCall):
    batch_date = payload.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    target_path = DATA_DIR / f"{batch_date}.csv"
    if not target_path.exists():
        return ToolResult(trace_id=payload.trace_id, status="NO_DATA", data=[])
    df = pd.read_csv(target_path)
    data = df.to_dict(orient="records")
    return ToolResult(trace_id=payload.trace_id, status="OK", data=data)

# 啟動 FastAPI 伺服器
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007)
