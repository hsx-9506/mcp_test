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
    days = int(payload.args.get("days", 7))
    end_date = datetime.now()
    start_date = end_date - pd.Timedelta(days=days-1)
    files = [f for f in Path(setting.ANOMALY_TREND_URL).glob("*.csv") if start_date.strftime("%Y-%m-%d") <= f.stem <= end_date.strftime("%Y-%m-%d")]
    all_df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True) if files else pd.DataFrame()
    if all_df.empty:
        return {"trace_id": payload.trace_id, "status": "NO_DATA", "data": []}
    trend = all_df.groupby('date').size().reset_index(name="anomaly_count")
    data = trend.to_dict(orient="records")
    return {"trace_id": payload.trace_id, "status": "OK", "data": data}
