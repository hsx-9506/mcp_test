#!/usr/bin/env python3
"""
batch_anomaly_server.py (最嚴謹MCP-L2版)

MCP-server：接收 tool_call，根據 batch_id 讀取 json_cache/ 下的 JSON，
自動判斷該批次有無異常（abnormal_flag），回傳整批檢驗摘要。

啟動方式：
  uvicorn mcp_server.batch_anomaly_server:app --host 0.0.0.0 --port 8001
"""

import config.setting as setting
import json
from pathlib import Path
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uuid

import json
from pathlib import Path

CACHE_DIR = Path(setting.DATA_CACHE)

# ──────────────────────────────────────
# MCP Tool Schema & Pydantic 模型
class ToolCall(BaseModel):
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool: str
    args: Dict[str, Any]

class ToolResult(BaseModel):
    trace_id: str
    status: str
    data: List[Dict[str, Any]]

# ──────────────────────────────────────
# FastAPI 伺服器

app = FastAPI(title="Batch Anomaly MCP-server")

@app.post("/tool_call", response_model=ToolResult)
def handle_tool_call(req: ToolCall):
    if req.tool != "batch_anomaly":
        raise HTTPException(400, "Unsupported tool")
    batch_id = req.args.get("batch_id")
    if not batch_id:
        raise HTTPException(400, "batch_id required")

    json_path = CACHE_DIR / f"{batch_id}.json"
    if not json_path.exists():
        raise HTTPException(404, f"Batch {batch_id} not found")

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            batch_data = json.load(f)
    except Exception as e:
        raise HTTPException(500, f"Failed to load batch: {e}")

    features = batch_data.get("features", [])
    meta = batch_data.get("meta", {})
    summary = batch_data.get("summary", {})

    abnormal_features = []
    for feat in features:
        if feat.get("cpk_alert") or feat.get("ppk_alert") or (feat.get("abnormal_detail") and len(feat.get("abnormal_detail")) > 0):
            abnormal_features.append({
                "feature_name": feat.get("feature_name"),
                "cpk": feat.get("cpk"),
                "ppk": feat.get("ppk"),
                "cpk_alert": feat.get("cpk_alert"),
                "cpk_reason": feat.get("cpk_reason"),
                "ppk_alert": feat.get("ppk_alert"),
                "ppk_reason": feat.get("ppk_reason"),
                "abnormal_detail": feat.get("abnormal_detail"),
            })

    has_abnormal = len(abnormal_features) > 0
    summary_result = {
        "batch_id": batch_id,
        "machine_id": meta.get("machine_id"),
        "product_name": summary.get("product_name"),
        "part_no": summary.get("part_no"),
        "vendor": summary.get("vendor"),
        "abnormal_count": len(abnormal_features),
        "abnormal_features": abnormal_features,
        "has_abnormal": has_abnormal,
        "type": "batch_anomaly_summary"
    }

    return ToolResult(
        trace_id=req.trace_id,
        status="OK",
        data=[summary_result]
    )

# ──────────────────────────────────────
# 主程式（可選）
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
