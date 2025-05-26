from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any, Dict
import config.setting as setting
import pandas as pd
from pathlib import Path
from datetime import datetime

app = FastAPI()

class ToolCall(BaseModel):
    trace_id: str
    tool: str
    args: Dict[str, Any]

@app.post("/tool_call")
def tool_call(payload: ToolCall):
    batch_date = payload.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    target_path = Path(setting.KPI_SUMMARY_URL) / f"{batch_date}.csv"
    if not target_path.exists():
        return {"trace_id": payload.trace_id, "status": "NO_DATA", "data": []}
    df = pd.read_csv(target_path)
    data = df.to_dict(orient="records")
    return {"trace_id": payload.trace_id, "status": "OK", "data": data}
