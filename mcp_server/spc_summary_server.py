#!/usr/bin/env python3
"""
spc_summary_server.py（嚴謹升級MCP-L2版）

自動彙整每批所有特徵的SPC能力統計（Cpk/Ppk），逐項判斷異常與明細，標準API回傳格式。
啟動方式：
  uvicorn mcp_server.spc_summary_server:app --host 0.0.0.0 --port 8002
"""

import config.setting as setting
from pathlib import Path
import json
from pathlib import Path
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uuid

CPK_PPK_THRESHOLD = 1.33   # 製程能力異常的閾值

CACHE_DIR = Path(setting.DATA_CACHE)

# MCP Tool Schema & Pydantic
class ToolCall(BaseModel):
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool: str
    args: Dict[str, Any]

class ToolResult(BaseModel):
    trace_id: str
    status: str
    data: List[Dict[str, Any]]

# FastAPI 伺服器
app = FastAPI(title="SPC Summary MCP-server")

@app.post("/tool_call", response_model=ToolResult)
def handle_tool_call(req: ToolCall):
    if req.tool != "spc_summary":
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

    spc_items = []
    abnormal_spc = []
    for feat in features:
        spc_item = {
            "feature_name": feat.get("feature_name"),
            "cpk": feat.get("cpk"),
            "ppk": feat.get("ppk"),
            "cpk_alert": feat.get("cpk_alert"),
            "cpk_reason": feat.get("cpk_reason"),
            "ppk_alert": feat.get("ppk_alert"),
            "ppk_reason": feat.get("ppk_reason"),
        }
        spc_items.append(spc_item)
        # 有任何異常都列為 abnormal_spc
        if (feat.get("cpk") is not None and feat.get("cpk") < CPK_PPK_THRESHOLD) or \
           (feat.get("ppk") is not None and feat.get("ppk") < CPK_PPK_THRESHOLD):
            abnormal_spc.append(spc_item)

    summary_result = {
        "batch_id": batch_id,
        "machine_id": meta.get("machine_id"),
        "product_name": summary.get("product_name"),
        "part_no": summary.get("part_no"),
        "vendor": summary.get("vendor"),
        "total_spc_items": len(spc_items),
        "abnormal_count": len(abnormal_spc),
        "abnormal_spc": abnormal_spc,
        "threshold": CPK_PPK_THRESHOLD,
        "has_abnormal_spc": bool(abnormal_spc),
        "spc_items": spc_items,
        "type": "spc_summary_result"
    }

    return ToolResult(
        trace_id=req.trace_id,
        status="OK",
        data=[summary_result]
    )

# 主程式（可選）
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
