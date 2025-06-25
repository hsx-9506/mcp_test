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

OPENAI_API_KEY = _settings["OPENAI_API_KEY"]
JSON_CACHE = _settings["JSON_CACHE"]
MOCK_DATA_PATH = _settings["MOCK_DATA_PATH"]
CPK_PPK_THRESHOLD = _settings["CPK_PPK_THRESHOLD"]
UNIFIED_SERVER_URL = _settings["UNIFIED_SERVER_URL"]
