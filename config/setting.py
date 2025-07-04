#!/usr/bin/env python3
"""
settings.py

MCP+LLM 專案全域參數與服務端點設定。
所有檔案路徑、API key、server 連線資訊統一集中管理。
"""

from pathlib import Path
import json
import os

# 載入 settings.json
SETTINGS_PATH = os.path.join(os.path.dirname(__file__), 'settings.json')
if os.path.exists(SETTINGS_PATH):
    with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
        _settings = json.load(f)
else:
    _settings = {}

# 從 _settings 中讀取所有設定值
OPENAI_API_KEY = _settings.get("OPENAI_API_KEY")
JSON_CACHE = _settings.get("JSON_CACHE")
MOCK_DATA_PATH = _settings.get("MOCK_DATA_PATH")
CPK_PPK_THRESHOLD = _settings.get("CPK_PPK_THRESHOLD")
UNIFIED_SERVER_URL = _settings.get("UNIFIED_SERVER_URL")

# ===== 新增的程式碼 =====
# 讀取 USE_MOCK_DATA 開關，如果 json 檔中沒有這個鍵，預設為 True (使用假資料)
USE_MOCK_DATA = _settings.get("USE_MOCK_DATA", True)