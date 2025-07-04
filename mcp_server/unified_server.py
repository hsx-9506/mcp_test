import json
from fastapi import FastAPI, Query
from typing import List, Optional
from fastapi.responses import JSONResponse
from collections import defaultdict, Counter # 引入 Counter
from config.setting import MOCK_DATA_PATH, CPK_PPK_THRESHOLD

app = FastAPI(title="Summary Server",
              description="提供各類生產數據的查詢和統計功能")

# 載入 mock data
with open(MOCK_DATA_PATH, 'r', encoding='utf-8') as f:
    DATA = json.load(f)

SUPPORTED_TYPES = [
    'production_summary', 'downtime_summary', 'yield_summary',
    'anomaly_trend', 'KPI_summary', 'issue_tracker',
    'batch_anomaly', 'spc_summary'
]

TYPE_FIELDS = {
    'production_summary': ['batch_id', 'machine_id', 'line', 'shift', 'target_qty', 'actual_qty', 'achieve_rate'],
    'downtime_summary': ['batch_id', 'machine_id', 'line', 'shift', 'event_count', 'total_minutes', 'main_reason', 'remark'],
    'yield_summary': ['batch_id', 'product', 'line', 'shift', 'good_qty', 'ng_qty', 'yield_percent'],
    # 趨勢分析著重於原因、地點、時間等聚合資訊
    'anomaly_trend': ['date', 'machine_id', 'line', 'event_type', 'main_reason', 'anomaly_remark', 'count'],
    'KPI_summary': ['batch_id', 'kpi_name', 'value', 'target', 'kpi_achieve_rate'],
    'issue_tracker': ['batch_id', 'issue_id', 'status', 'owner', 'created_at', 'closed_at', 'description'],
    # 批次異常維持原樣，提供最完整的單一批次資訊
    'batch_anomaly': [
        'batch_id', 'product', 'machine_id', 'date', 'abnormal_count', 'abnormal_features',
        'main_reason', 'anomaly_remark', 'spc_items', 'ng_qty', 'good_qty'
    ],
    # SPC查詢專注於回傳包含製程能力指標的項目
    'spc_summary': [
        'batch_id', 'product', 'machine_id', 'date', 'spc_items'
    ]
}

def is_abnormal(row):
    # 綜合異常判斷
    if row.get('abnormal_count', 0) > 0:
        return True
    if row.get('event_count', 0) > 0:
        return True
    if row.get('ng_qty', 0) > 0:
        return True
    if row.get('event_type'):
        return True
    if row.get('status') == 'open':
        return True
    if row.get('kpi_achieve_rate', 100) < 90:
        return True
    return False

def is_spc_abnormal(row):
    for spc in row.get('spc_items', []):
        if (spc.get('cpk', 99) < CPK_PPK_THRESHOLD) or (spc.get('ppk', 99) < CPK_PPK_THRESHOLD):
            return True
        if spc.get('cpk_alert') or spc.get('ppk_alert'):
            return True
    return False

def is_batch_abnormal(row):
    return bool(row.get('abnormal_features'))

@app.get("/api/query")
def query_server(
    type: str = Query(..., description="查詢型別"),
    batch_id: Optional[str] = Query(None),
    machine_id: Optional[str] = Query(None),
    product: Optional[str] = Query(None),
    shift: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    abnormal_only: Optional[bool] = Query(False),
    spc_abnormal_only: Optional[bool] = Query(False),
    batch_abnormal_only: Optional[bool] = Query(False),
    group_by: Optional[str] = Query(None),
    fields: Optional[str] = Query(None, description="動態欄位, 逗號分隔"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500)
):
    if type not in SUPPORTED_TYPES:
        return {"status": "error", "msg": f"不支援的查詢型別: {type}"}
    
    # 動態欄位
    use_fields = TYPE_FIELDS.get(type, [])
    if fields:
        use_fields = [f.strip() for f in fields.split(',') if f.strip()]
    
    if type == 'anomaly_trend':
        trend_data = []
        # 從原始數據中提取所有與趨勢相關的事件紀錄
        for row in DATA:
            # 我們認為，只要 'anomaly_remark' 存在，就代表一筆值得分析的歷史事件
            if row.get('anomaly_remark'):
                trend_item = {k: row.get(k) for k in use_fields if k in row}
                # 確保 'count' 欄位存在，若無則預設為 1
                if 'count' not in trend_item or not trend_item['count']:
                    trend_item['count'] = 1
                trend_data.append(trend_item)
        
        return JSONResponse({
            "status": "ok",
            "type": "anomaly_trend",
            "total": len(trend_data),
            "data": trend_data
        })

    # 過濾
    result = []
    for row in DATA:
        if batch_id and row.get('batch_id') != batch_id: continue
        if machine_id and row.get('machine_id') != machine_id: continue
        if product and row.get('product') != product: continue
        if shift and row.get('shift') != shift: continue
        if date and row.get('date') != date: continue
        if status and row.get('status') != status: continue
        if abnormal_only and not is_abnormal(row): continue
        if batch_abnormal_only and not is_batch_abnormal(row): continue

        # spc_abnormal_only 是一個通用的篩選器
        if spc_abnormal_only and not is_spc_abnormal(row):
            continue
        
        # 而當查詢類型本身就是 spc_summary 時，我們強制只回傳有SPC異常的批次
        if type == 'spc_summary' and not is_spc_abnormal(row):
            continue

        filtered = {k: row.get(k, None) for k in use_fields}
        result.append(filtered)
    
    # 分群/分組
    if group_by and group_by in use_fields:
        group_dict = defaultdict(list)
        for r in result:
            group_dict[r.get(group_by)].append(r)
        # 統計每群異常數、總數
        group_stats = {}
        for g, items in group_dict.items():
            group_stats[g] = {
                'total': len(items),
                'abnormal': sum(1 for i in items if i['is_abnormal']),
                'spc_abnormal': sum(1 for i in items if i['is_spc_abnormal']),
                'batch_abnormal': sum(1 for i in items if i['is_batch_abnormal']),
                'items': items
            }
        return JSONResponse({"status": "ok", "type": type, "group_by": group_by, "group_stats": group_stats})
    # 分頁
    total = len(result)
    start = (page-1)*size
    end = start+size
    paged = result[start:end]

    return JSONResponse({
        "status": "ok",
        "type": type,
        "total": total,
        "page": page,
        "size": size,
        "data": paged
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
