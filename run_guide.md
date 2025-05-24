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

本系統需要 LLM API 金鑰，請申請並設為環境變數。

#### Windows 命令提示字元

```cmd
set OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

#### settings.json檔案

請於 `settings.json` 檔案中設定 `"OPENAI_API_KEY": "sk-xxxxxxx"`

> 請將 `sk-xxxxxxxx` 替換為你的 OpenAI 真實 API 金鑰

---

## 3. 資料前處理（Excel ➔ JSON）

本專案預設資料夾為 `D:/project/20250430產品出貨SPC/`。請確認有放置所有欲分析的 Excel 檔案。

### 3.1 批次轉換全部 Excel

```bash
python edge_etl/etl_to_json.py
```

> 轉換後資料會自動存入 `json_cache/` 供 MCP-server 讀取加速查詢
> 若加 `--export-json`，會同時產出批次的 JSON 檔

---

## 4. 啟動 MCP-server 多工具服務

請開**兩個命令視窗**，各自啟動下列服務：

### 4.1 啟動批次異常分析服務

```bash
uvicorn mcp_server.batch_anomaly_server:app --host 0.0.0.0 --port 8001
```

### 4.2 啟動 SPC 製程能力檢查服務

```bash
uvicorn mcp_server.spc_summary_server:app --host 0.0.0.0 --port 8002
```

> 若需變更 port 或加參數，請修改 `settings.py` 內對應設定
> 每個服務預設會從 `json_cache/` 讀取資料

---

## 5. 啟動 LLM 多工具 Agent 整合查詢

此步驟將由 LLM 進行語意拆解、發出多個 tool\_call，整合所有 MCP-server 回覆並輸出建議。

```bash
python llm_agent.py --batch D42991
```

> 請將 `D42991` 改為你想分析的實際批次號（或產品批次關鍵字）

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
  * 修改 `settings.py` 或主程式中 `DATA_DIR` 參數。

* **LLM 無回應：**
  * 檢查 API 配額與金鑰。

---

## 8. 簡易流程圖

資料前處理（Excel → JSON 快取）
　　↓
啟動 MCP 多工具服務（批次異常 / SPC）
　　↓
LLM 拆解問題、發多次 tool\_call → 串接 MCP-server
　　↓
LLM 統一回覆異常分析與改善建議
　　↓
終端機輸出完整回應

---

## 9. 重要檔案說明

* `etl_to_json.py`：批次轉換 Excel → JSON
* `batch_anomaly_server.py`：批次異常分析 REST 服務
* `spc_summary_server.py`：SPC 製程能力檢查 REST 服務
* `llm_agent.py`：自動語意拆解、發 tool\_call、整合回應
* `settings.py`：全域參數（含 API 路徑、資料夾）
* `json_cache/`：所有前處理好的 JSON 批次資料

---

## 備註

* 可於 `settings.py`/`settings.json` 調整資料目錄、API 端點、快取策略等參數。
* 若需支援資料庫/Redis/向量庫，請參考擴充說明或聯繫開發者。
* 建議以 Python 3.9+ 執行本專案。
* 建議於虛擬環境（venv/conda）安裝測試。
