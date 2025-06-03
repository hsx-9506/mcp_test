# MCP+LLM 智慧製造異常分析快速操作指南

> 本指南說明如何從資料前處理（ETL）、啟動 MCP 多工具服務，到 LLM 智慧整合異常分析的整個操作步驟與指令。

---

## 1. 安裝相依套件

請於專案根目錄輸入以下指令，安裝所有必要 Python 套件（**只需做一次**）：

```bash
pip install -r requirements.txt
```

> 如未安裝 pip，請先參考[官方說明](https://pip.pypa.io/en/stable/installation/)

---

## 2. 設定 OpenAI API 金鑰

本系統需要 LLM API 金鑰，請申請並設為環境變數或於設定檔中填寫。

#### Windows 命令提示字元

```cmd
set OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

#### 或於 settings.json 檔案設定

請於 `config/settings.json` 檔案中設定 `"OPENAI_API_KEY": "sk-xxxxxxx"`

> 請將 `sk-xxxxxxxx` 替換為你的 OpenAI 真實 API 金鑰

---

## 3. 資料前處理（Excel ➔ JSON）

請將所有欲分析的 Excel 檔案放入預設資料夾（如 `20250430產品出貨SPC/`）。

### 3.1 批次轉換全部 Excel

```bash
python edge_etl/etl_to_json.py
# 或
python edge_etl/etl_to_json.py --batch <批次關鍵字>
```

> 轉換後資料會自動存入 `mcp_server/json_cache/` 供 MCP-server 讀取加速查詢

---

## 4. 啟動 MCP-server 多工具服務

請分別於多個命令視窗啟動下列服務（可依需求選擇）：

```bash
uvicorn mcp_server.batch_anomaly_server:app --host 0.0.0.0 --port 8001
uvicorn mcp_server.spc_summary_server:app --host 0.0.0.0 --port 8002
uvicorn mcp_server.production_summary_server:app --host 0.0.0.0 --port 8003
uvicorn mcp_server.downtime_summary_server:app --host 0.0.0.0 --port 8004
uvicorn mcp_server.yield_summary_server:app --host 0.0.0.0 --port 8005
uvicorn mcp_server.anomaly_trend_server:app --host 0.0.0.0 --port 8006
uvicorn mcp_server.KPI_summary_server:app --host 0.0.0.0 --port 8007
uvicorn mcp_server.issue_tracker_server:app --host 0.0.0.0 --port 8008
```

> 每個服務預設會從 `mcp_server/json_cache/` 讀取資料。  
> 若需變更 port 或資料來源，請修改 `config/settings.json` 或 `config/setting.py`。

---

## 5. 啟動 LLM 多工具 Agent 整合查詢

此步驟將由 LLM 進行語意拆解、發出多個 tool_call，整合所有 MCP-server 回覆並輸出建議。

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

---

## 6. 查看 LLM 分析回覆

LLM agent 執行結束後，終端機將自動輸出異常原因、SPC 結果、與建議。

---

## 7. 進階/常見問題

* **如果出現「找不到檔案」或「JSON 不存在」錯誤：**
  * 請先確認已執行 `etl_to_json.py` 做前處理。

* **API 金鑰錯誤或 401 Unauthorized：**
  * 檢查 `OPENAI_API_KEY` 是否設定正確。

* **出現 404/500 或 port 佔用：**
  * 檢查 server 是否成功啟動，且無其他程式佔用對應 port。

* **欲更換資料來源/Excel 路徑：**
  * 修改 `config/settings.json` 或主程式中 `DATA_DIR` 參數。

* **LLM 無回應：**
  * 檢查 API 配額與金鑰。

---

> 詳細專案架構、功能說明與檔案介紹請參考 [README.md](README.md)
