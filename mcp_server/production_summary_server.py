#!/usr/bin/env python3
"""
production_summary_server.py

自動彙整指定日期的生產數據，回傳每台機台、產線、班別的目標產量、實際產量與達成率。
標準 API 回傳格式，支援 LLM 多工具自動化查詢。

啟動方式：
  uvicorn mcp_server.production_summary_server:app --host 0.0.0.0 --port 8003
"""

import config.setting as setting
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uuid

# 設定資料來源資料夾
DATA_DIR = Path(setting.MOCK_PRODUCTION_SUMMARY)

# MCP Tool Schema & Pydantic 模型
class ToolCall(BaseModel):
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool: str
    args: Dict[str, Any]

# ToolResult Schema
class ToolResult(BaseModel):
    trace_id: str
    status: str
    data: List[Dict[str, Any]]

# 建立 FastAPI 伺服器
app = FastAPI(title="Production Summary MCP-server")

# 路由：處理工具呼叫
@app.post("/tool_call", response_model=ToolResult)
def handle_tool_call(req: ToolCall):
    if req.tool != "production_summary":
        raise HTTPException(400, "Unsupported tool")
    date = req.args.get("date")
    if not date:
        raise HTTPException(400, "date required")

    csv_path = DATA_DIR / f"{date}.csv"
    if not csv_path.exists():
        raise HTTPException(404, f"No production data for {date}")

    try:
        df = pd.read_csv(csv_path, encoding="utf-8")
    except Exception as e:
        raise HTTPException(500, f"Failed to read production data: {e}")

    records = df.to_dict(orient="records")
    return ToolResult(
        trace_id=req.trace_id,
        status="OK",
        data=records
    )

# 啟動 FastAPI 伺服器
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
