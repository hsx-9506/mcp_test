import config.setting as setting
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uuid
from datetime import datetime, timedelta

# Anomaly Trend Server
# 自動彙整指定日期的異常趨勢資料，回傳所有產品/產線/班別的異常統計。
DATA_DIR = Path(setting.MOCK_ANOMALY_TREND)

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
app = FastAPI(title="Anomaly Trend MCP-server")

# 將字串轉為 datetime 物件
def parse_date(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d")

# 路由：處理工具呼叫
@app.post("/tool_call", response_model=ToolResult)
def handle_tool_call(req: ToolCall):
    if req.tool != "anomaly_trend":
        raise HTTPException(400, "Unsupported tool")
    start_date = req.args.get("start_date")
    end_date = req.args.get("end_date", start_date)
    if not start_date:
        raise HTTPException(400, "start_date required")

    try:
        start_dt = parse_date(start_date)
        end_dt = parse_date(end_date)
    except Exception:
        raise HTTPException(400, "日期格式錯誤，請用YYYY-MM-DD")

    all_records = []
    curr_dt = start_dt
    while curr_dt <= end_dt:
        date_str = curr_dt.strftime("%Y-%m-%d")
        csv_path = DATA_DIR / f"{date_str}.csv"
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path, encoding="utf-8")
                for row in df.to_dict(orient="records"):
                    row["date"] = date_str
                    all_records.append(row)
            except Exception:
                pass
        curr_dt += timedelta(days=1)

    return ToolResult(
        trace_id=req.trace_id,
        status="OK",
        data=all_records
    )

# 啟動 FastAPI 伺服器
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
