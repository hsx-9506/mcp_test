#!/usr/bin/env python3
"""
settings.py

MCP+LLM 專案全域參數與服務端點設定。
所有檔案路徑、API key、server 連線資訊統一集中管理。
"""

import os
import json
from pathlib import Path

# 讀取 settings.json
def load_json(fp):
    with open(fp, 'r', encoding='utf-8') as f:
        return json.load(f)

SETTINGS_PATH = Path("config/settings.json")
config = load_json(SETTINGS_PATH)

# 資料來源資料夾 (ETL、原始 Excel)
DATA_SRC = config["DATA_SRC"]

# JSON cache 存放目錄（供 MCP-server 查詢）
JSON_CACHE = config["JSON_CACHE"]

# LLM 回覆模板
INTENT_CONFIG = config["INTENT_CONFIG"]

# MCP server endpoints
BATCH_ANOMALY_URL = config["BATCH_ANOMALY_URL"]
SPC_SUMMARY_URL = config["SPC_SUMMARY_URL"]
PRODUCTION_SUMMARY_URL = config["PRODUCTION_SUMMARY_URL"]
DOWNTIME_SUMMARY_URL = config["DOWNTIME_SUMMARY_URL"]
YIELD_SUMMARY_URL = config["YIELD_SUMMARY_URL"]
ANOMALY_TREND_URL = config["ANOMALY_TREND_URL"]
KPI_SUMMARY_URL = config["KPI_SUMMARY_URL"]
ISSUE_TRACKER_URL = config["ISSUE_TRACKER_URL"]

# LLM 參數
OPENAI_API_KEY = config["OPENAI_API_KEY"]

# 製程能力門檻（SPC）
CPK_PPK_THRESHOLD = 1.33

# Excel 標準檔案名稱規則
EXCEL_PATTERN = "*.xlsx"

# 其他可擴充設定...
