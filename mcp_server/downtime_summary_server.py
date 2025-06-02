#!/usr/bin/env python3
"""
downtime_summary_server.py

自動彙整指定日期的設備停機資料，回傳所有停機紀錄（可含機台、產線、停機時數等）。
標準 API 回傳格式，支援 LLM 多工具自動化查詢。
啟動方式：
  uvicorn mcp_server.downtime_summary_server:app --host 0.0.0.0 --port 8004
"""

import config.setting as setting
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uuid

# 設定停機資料來源目錄
DATA_DIR = Path(setting.DOWNTIME_SUMMARY_URL)

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

# FastAPI 伺服器
app = FastAPI(title="Downtime Summary MCP-server")

# 路由：處理工具呼叫
@app.post("/tool_call", response_model=ToolResult)
def handle_tool_call(req: ToolCall):
    if req.tool != "downtime_summary":
        raise HTTPException(400, "Unsupported tool")
    date = req.args.get("date")
    if not date:
        raise HTTPException(400, "date required")

    csv_path = DATA_DIR / f"{date}.csv"
    if not csv_path.exists():
        raise HTTPException(404, f"No downtime data for {date}")

    try:
        df = pd.read_csv(csv_path, encoding="utf-8")
    except Exception as e:
        raise HTTPException(500, f"Failed to read downtime data: {e}")

    # 可進一步篩選/排序（如取停機時數TOP N、篩某產線等）
    records = df.to_dict(orient="records")
    # 預設全部回傳，建議由 agent/LLM 再排序/摘要
    return ToolResult(
        trace_id=req.trace_id,
        status="OK",
        data=records
    )

# 啟動 FastAPI 伺服器
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
