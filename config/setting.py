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
with open(".vscode/settings.json", "r", encoding="utf-8") as f:
    _config = json.load(f)

# 資料來源資料夾 (ETL、原始 Excel)
DATA_DIR = _config["DATA_DIR"]

# JSON cache 存放目錄（供 MCP-server 查詢）
JSON_CACHE_DIR = _config["DATA_CACHE"]

# MCP server endpoints
BATCH_ANOMALY_URL = _config["BATCH_ANOMALY_URL"]
SPC_SUMMARY_URL = _config["SPC_SUMMARY_URL"]

# LLM 參數
OPENAI_API_KEY = _config["OPENAI_API_KEY"]

# 製程能力門檻（SPC）
CPK_PPK_THRESHOLD = 1.33

# Excel 標準檔案名稱規則
EXCEL_PATTERN = "*.xlsx"

# 其他可擴充設定...
