# 智慧製造資料前處理與 LLM 多工具呼叫測試系統

本專案旨在結合 MCP（Model Context Protocol）多 Agent 架構與大型語言模型（LLM），
對製造產線批次資料進行前置 ETL、異常分析、製程能力檢查（SPC），
實現智慧問答與多源自動查詢推薦。

## 目錄結構
.
├── etl_to_json.py # 將 Excel ETL 成標準 JSON，儲存至 json_cache/
├── batch_anomaly_server.py # MCP-server：批次異常分析工具
├── spc_summary_server.py # MCP-server：SPC summary 製程能力檢查工具
├── llm_agent.py # LLM agent：拆解多子任務、串多 server、總整問答
├── settings.py # 全域參數與 server 端點設定
├── requirements.txt
├── mcp_server/
│ └── json_cache/ # 各批次 JSON 統一存放
└── D:/project/20250430產品出貨SPC/ # (原始 Excel 資料)

## 功能流程

1. **資料前處理（ETL）**
   - `etl_to_json.py` 會將每批 Excel 轉成結構化 JSON，預先過濾、彙整並存入 `json_cache/`。

2. **MCP-server 子服務**
   - `batch_anomaly_server.py`：回應單批異常統計與明細。
   - `spc_summary_server.py`：回應單批 SPC（Cpk, Ppk）製程能力摘要。

3. **多工具 LLM agent**
   - `llm_agent.py` 會模擬 LLM 分析問題 → 拆解子任務 → 發出多個 tool_call → 串接所有 MCP-server 回覆，整合統一回答。

## 安裝說明

1. **安裝必要套件**

    ```bash
    pip install -r requirements.txt
    ```

2. **準備 OpenAI API 金鑰**

    - 設定環境變數：
      ```bash
      export OPENAI_API_KEY=sk-xxxxxx  # Linux/Mac
      ```
      或在 Windows cmd：
      ```cmd
      set OPENAI_API_KEY=sk-xxxxxx
      ```

    - 或以 `settings.json` 搭配 `settings.py` 讀取。

3. **資料前處理**
    ```bash
    python etl_to_json.py --all
    # 或
    python etl_to_json.py --batch <批次關鍵字>
    ```

4. **啟動 MCP-server 子服務**
    ```bash
    uvicorn batch_anomaly_server:app --host 0.0.0.0 --port 8001
    uvicorn spc_summary_server:app   --host 0.0.0.0 --port 8002
    ```

5. **執行 LLM 多工具整合問答**
    ```bash
    python llm_agent.py --batch <批次關鍵字>
    ```

## 主要檔案說明

- **etl_to_json.py**：資料前處理（ETL），將所有 Excel 整批轉換成 JSON，便於 MCP server 高效查詢。
- **batch_anomaly_server.py**：查詢批次各項目異常狀態。
- **spc_summary_server.py**：查詢製程能力指標，判斷有無 SPC 異常。
- **llm_agent.py**：模擬 LLM 將用戶問題拆解為多個子工具調用，串多 server 回傳給 LLM 統一分析。
- **settings.py**：全域參數設定，方便多程式共用與集中管理。

## 專案特色

- **結構化資料交換**：所有 MCP 服務採標準 JSON，跨模組/平台易於整合。
- **分層快取**：ETL 統一快取減少重算負擔，支援本地/雲端大規模查詢。
- **多工具自動拆解/整合**：LLM agent 可自動分派任務並聚合多工具回應，適用各種複雜異常或決策分析情境。
- **易擴充/模組化**：MCP-server 可輕鬆增加自訂新功能，支援更多資料源或智能工具。

## 其他

- 請確保所有路徑、API 金鑰與 Python 版本正確。
- 若需串接資料庫或 Redis 快取，請於 `settings.py` 擴充對應參數與連線程式。

---

如有專案問題或功能建議，請於 issues 或 PR 提出！
