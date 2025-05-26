from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any, Dict
import config.setting as setting
import pandas as pd
from pathlib import Path

app = FastAPI()

class ToolCall(BaseModel):
    trace_id: str
    tool: str
    args: Dict[str, Any]

@app.post("/tool_call")
def tool_call(payload: ToolCall):
    target_path = Path(setting.ISSUE_TRACKER_URL) / "issues.csv"
    if not target_path.exists():
        return {"trace_id": payload.trace_id, "status": "NO_DATA", "data": []}
    df = pd.read_csv(target_path)
    # 未結案
    not_closed = df[df['status'] != 'closed']
    data = not_closed.to_dict(orient="records")
    return {"trace_id": payload.trace_id, "status": "OK", "data": data}
