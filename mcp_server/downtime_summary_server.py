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
    top_n = int(payload.args.get("top", 5))
    target_path = Path(setting.DOWNTIME_SUMMARY_URL) / f"{batch_date}.csv"
    if not target_path.exists():
        return {"trace_id": payload.trace_id, "status": "NO_DATA", "data": []}
    df = pd.read_csv(target_path)
    # 彙總停機事件
    grouped = df.groupby('machine_id').agg(
        downtime_count=('downtime_minutes', 'count'),
        downtime_total=('downtime_minutes', 'sum'),
        main_reason=('reason', lambda x: x.mode()[0] if not x.mode().empty else "")
    ).reset_index()
    data = grouped.sort_values('downtime_total', ascending=False).head(top_n).to_dict(orient="records")
    return {"trace_id": payload.trace_id, "status": "OK", "data": data}
