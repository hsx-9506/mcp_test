# 智慧製造資料前處理與 LLM 多工具呼叫測試系統

本專案結合 MCP（Model Context Protocol）多 Agent 架構與大型語言模型（LLM），
針對製造產線批次資料進行前置 ETL、異常分析、製程能力檢查（SPC）、產能/停機/良率/異常趨勢等多面向查詢，
實現智慧問答、語意自動拆解與多源查詢推薦。

## 目錄結構
<pre>
MCP_TEST
│
├─ 20250430產品出貨SPC/           # 原始Excel資料
│
├─ agent_client/                  # LLM Agent 端（主流程）
│   └─ llm_agent.py
│
├─ config/                        # 設定/共用設定模組
│   ├─ __init__.py
│   ├─ prompts.py
│   ├─ setting.py
│   └─ settings.json
│
├─ edge_etl/                      # 邊緣端ETL/前處理
│   └─ etl_to_json.py
│
├─ mcp_server/                    # MCP伺服器API與快取
│   ├─ json_cache/                # 批次快取資料
│   └─ unified_server.py          # 統合型查詢API
│
├─ mock_data/                     # 測試/模擬資料
│   ├─ all_server_full_mock_data.json
│   └─ gen_all_server_full_mock_data.py
│
├─ ui.py                          # 圖形化查詢介面（Tkinter）
├─ requirements.txt               # Python依賴
├─ README.md                      # 專案說明
└─ run_guide.md                   # 操作手冊/快速指南
</pre>

## 主要功能流程

1. **資料前處理（ETL）**
   - `edge_etl/etl_to_json.py`：將每批 Excel 轉成結構化 JSON，預先過濾、彙整並存入 `mcp_server/json_cache/`。

2. **MCP-server 啟動**
   - `mcp_server/unified_server.py`：統合所有查詢、異常、統計、分群、分頁、動態欄位等功能，支援 type 參數查詢多 server 欄位，設定集中管理。

3. **LLM Agent 智能查詢**
   - `agent_client/llm_agent.py`：
     - 支援自然語言查詢自動語意拆解、tool_call 拆解、查詢 unified_server、摘要與 LLM 回饋。
     - 設定集中管理，所有查詢流程自動化。
     - 可由 CLI、UI 或其他程式直接呼叫。

4. **圖形化查詢介面**
   - `ui.py`：Tkinter UI，支援查詢流程可視化、每階段狀態與摘要顯示。

## 重要檔案說明

- `edge_etl/etl_to_json.py`：資料前處理（ETL），將 Excel 轉換成 JSON。
- `agent_client/llm_agent.py`：主 agent，語意拆解、tool_call、查詢 unified_server、摘要與 LLM 回饋。
- `config/setting.py, settings.json`：全域參數設定，含 unified_server 位置、API KEY 等。
- `mcp_server/unified_server.py`：統合型 MCP server，所有查詢/異常/統計/分群/分頁/動態欄位等功能。
- `mock_data/all_server_full_mock_data.json`：全功能 mock data。
- `ui.py`：Tkinter 圖形化查詢介面。

## 操作說明

詳細安裝、啟動、查詢與開發流程請參考 [run_guide.md](run_guide.md)。

## 特色與擴充
- 支援多種查詢類型（異常、SPC、產能、停機、良率、KPI、缺陷追蹤等）。
- 語意自動拆解、tool_call 自動發送、摘要與 LLM 回饋全自動。
- 設定集中管理，mock data 可彈性切換。
- UI/CLI 皆可操作，易於展示與擴充。

---
如需進階串接資料庫/Redis/向量庫，請參考 run_guide.md 或聯繫開發者。