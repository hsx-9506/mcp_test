# 智慧製造資料前處理與 LLM 多工具呼叫測試系統

本專案旨在結合 MCP（Model Context Protocol）多 Agent 架構與大型語言模型（LLM），
對製造產線批次資料進行前置 ETL、異常分析、製程能力檢查（SPC），
實現智慧問答與多源自動查詢推薦。

## 目錄結構
<pre>
MCP_TEST
│
├─ .venv/                         # Python 虛擬環境
├─ .vscode/                       # VSCode 開發設定
│   └─ launch.json
│
├─ 20250430產品出貨SPC/           # 原始Excel資料
│
├─ agent_client/                  # LLM Agent 端
│   └─ llm_agent.py
│
├─ config/                        # 設定/共用設定模組
│   ├─ __init__.py
│   ├─ setting.py
│   └─ settings.json
│
├─ edge_etl/                      # 邊緣端ETL/前處理
│   └─ etl_to_json.py
│
├─ intent_config/                 # LLM意圖與工具設定
│   └─ intents.json
│
├─ mcp_server/                    # MCP伺服器API與快取
│   ├─ __pycache__/
│   ├─ json_cache/                # 批次快取資料
│   ├─ anomaly_trend_server.py
│   ├─ batch_anomaly_server.py
│   ├─ downtime_summary_server.py
│   ├─ issue_tracker_server.py
│   ├─ KPI_summary_server.py
│   ├─ production_summary_server.py
│   ├─ spc_summary_server.py
│   └─ yield_summary_server.py
│
├─ mock_data/                     # 測試/模擬資料根目錄
│   ├─ downtime_summary/          # 停機資料
│   ├─ issue_tracker/             # 缺陷/異常追蹤資料
│   ├─ KPI_summary/               # KPI資料
│   ├─ production_summary/        # 生產數據
│   └─ yield_summary/             # 良率資料
│
├─ .gitignore                     # Git忽略規則
├─ README.md                      # 專案說明
├─ requirements.txt               # Python依賴
└─ run_guide.md                   # 操作手冊/快速指南
</pre>

## 主要功能流程

1. **資料前處理（ETL）**
   - `edge_etl/etl_to_json.py`：將每批 Excel 轉成結構化 JSON，預先過濾、彙整並存入 `mcp_server/json_cache/`。

2. **MCP-server 啟動**
   - 各類 server 依據需求啟動，提供批次異常、SPC、產能、停機、良率、異常趨勢、KPI、缺陷追蹤等查詢 API。

3. **LLM Agent 整合查詢**
   - `agent_client/llm_agent.py`：根據意圖自動拆解子問題、呼叫多 server 並彙整重點摘要後餵給 LLM，產生專業建議。

## 重要檔案說明

- `edge_etl/etl_to_json.py`：資料前處理（ETL），將 Excel 轉換成 JSON。
- `agent_client/llm_agent.py`：LLM agent，根據意圖自動拆解子問題、呼叫多 server 並彙整重點摘要後餵給 LLM。
- `intent_config/intents.json`：定義 LLM 可用工具與參數。
- `config/setting.py, settings.json`：全域參數設定。
- `mcp_server/*.py`：各類 MCP server，負責不同資料查詢與摘要。
- `mcp_server/json_cache/`：所有前處理好的 JSON 批次資料。

## 進階/常見問題

- 詳細操作與啟動流程請參考 [run_guide.md](run_guide.md)。
- 若需支援資料庫/Redis/向量庫，請參考擴充說明或聯繫開發者。
- 建議以 Python 3.9+ 執行本專案，並於虛擬環境（venv/conda）安裝測試。