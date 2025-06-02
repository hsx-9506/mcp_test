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
├─ .gitignore                     # Git忽略規則
├─ README.md                      # 專案說明
├─ requirements.txt               # Python依賴
└─ run_guide.md                   # 操作手冊/快速指南
</pre>

## 功能流程

1. **資料前處理（ETL）**
   - `edge_etl/etl_to_json.py`：將每批 Excel 轉成結構化 JSON，預先過濾、彙整並存入 `mcp_server/json_cache/`。

2. **MCP-server 子服務**
   - `mcp_server/` 目錄下各 server 檔案分別負責不同資料查詢與摘要服務，皆以 FastAPI 啟動。

3. **多工具 LLM agent**
   - `agent_client/llm_agent.py`：模擬 LLM 分析問題 → 拆解子任務 → 發出多個 tool_call → 串接所有 MCP-server 回覆，整合統一回答。

4. **意圖與工具設定**
   - `intent_config/intents.json`：定義 LLM 可用的工具（server）與參數，支援彈性擴充。

## 安裝與執行

1. **安裝必要套件**
    ```bash
    pip install -r requirements.txt
    ```

2. **準備 LLM API 金鑰**
    - Windows cmd 設定環境變數：
      ```cmd
      set OPENAI_API_KEY=sk-xxxxxx
      ```
    - 或直接在 `config/settings.json` 設定 `"OPENAI_API_KEY"`。

3. **資料前處理**
    ```bash
    python edge_etl/etl_to_json.py
    # 或
    python edge_etl/etl_to_json.py --batch <批次關鍵字>
    ```

4. **啟動 MCP-server 子服務（可多開）**
    ```bash
    uvicorn mcp_server.batch_anomaly_server:app --host 0.0.0.0 --port 8001
    uvicorn mcp_server.spc_summary_server:app --host 0.0.0.0 --port 8002
    uvicorn mcp_server.production_summary_server:app --host 0.0.0.0 --port 8003
    uvicorn mcp_server.downtime_summary_server:app --host 0.0.0.0 --port 8004
    uvicorn mcp_server.yield_summary_server:app --host 0.0.0.0 --port 8005
    uvicorn mcp_server.anomaly_trend_server:app --host 0.0.0.0 --port 8006
    uvicorn mcp_server.KPI_summary_server:app --host 0.0.0.0 --port 8007
    uvicorn mcp_server.issue_tracker_server:app --host 0.0.0.0 --port 8008
    # 其他 server 依需求啟動
    ```

5. **執行 LLM 多工具整合問答**
    - 處理全部批次：
      ```bash
      python -m agent_client.llm_agent
      ```
    - 處理指定批次：
      ```bash
      python -m agent_client.llm_agent --batch 02,03,05
      ```
    - 指定意圖（如有多種 intent）：
      ```bash
      python -m agent_client.llm_agent --intent 查詢批次異常
      ```

## 主要檔案說明

- **edge_etl/etl_to_json.py**：資料前處理（ETL），將 Excel 轉換成 JSON。
- **agent_client/llm_agent.py**：LLM agent，根據意圖自動拆解子問題、呼叫多 server 並彙整重點摘要後餵給 LLM。
- **intent_config/intents.json**：定義 LLM 可用工具與參數。
- **config/setting.py, settings.json**：全域參數設定。
- **mcp_server/*.py**：各類 MCP server，負責不同資料查詢與摘要：
  - `batch_anomaly_server.py`：批次異常檢查與摘要。
  - `spc_summary_server.py`：SPC 製程能力統計與異常判斷。
  - `production_summary_server.py`：生產數量與產能彙總。
  - `downtime_summary_server.py`：設備停機與異常時段彙整。
  - `yield_summary_server.py`：良率統計與異常批次分析。
  - `anomaly_trend_server.py`：異常趨勢與歷史比對。
  - `KPI_summary_server.py`：關鍵績效指標（KPI）彙總。
  - `issue_tracker_server.py`：異常/缺陷追蹤與處理紀錄。

## 專案特色

- **結構化資料交換**：所有 MCP 服務採標準 JSON，跨模組/平台易於整合。
- **分層快取**：ETL 統一快取減少重算負擔，支援本地/雲端大規模查詢。
- **多工具自動拆解/整合**：LLM agent 可自動分派任務並聚合多工具回應，適用各種複雜異常或決策分析情境。
- **易擴充/模組化**：MCP-server 可輕鬆增加自訂新功能，支援更多資料源或智能工具。

## 其他

- 請確保所有路徑、API 金鑰與 Python 版本正確。
- 若需串接資料庫或 Redis 快取，請於 `settings.py` 擴充對應參數與連線程式。

---