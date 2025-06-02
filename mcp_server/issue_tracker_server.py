from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any, Dict, List
import config.setting as setting
import pandas as pd
from pathlib import Path
import uuid

# Issue Tracker Server
DATA_DIR = Path(setting.MOCK_ISSUE_TRACKER)

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
    target_path = DATA_DIR / "issues.csv"
    if not target_path.exists():
        return ToolResult(trace_id=payload.trace_id, status="NO_DATA", data=[])
    df = pd.read_csv(target_path)
    not_closed = df[df['status'] != 'closed']
    data = not_closed.to_dict(orient="records")
    return ToolResult(trace_id=payload.trace_id, status="OK", data=data)

# 啟動 FastAPI 伺服器
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8008)
