# API 接口规范 (API_SPEC)

## 基础信息
- Base URL: `http://localhost:8000`
- 数据格式: JSON

## REST API

### GET /api/health
健康检查

**响应** `200`:
```json
{"status": "ok", "version": "0.1.0"}
```

### POST /api/upload
上传 CSV/Excel 文件

**请求**: multipart/form-data, file字段
**响应** `200`:
```json
{
  "data_source_id": "uuid",
  "name": "文件名",
  "table_name": "ds_xxx",
  "row_count": 100,
  "columns_meta": [{"name": "金额", "dtype": "float64", "null_count": 0}],
  "validation_report": {"overall_score": 95.0, "issues": []}
}
```
**错误** `400`: 格式不支持或文件过大

### GET /api/data-sources
数据源列表

**响应** `200`: `[{id, name, table_name, row_count, columns_meta, created_at}]`

### GET /api/data-sources/{id}
数据源详情

**响应** `200`: 单个数据源对象
**错误** `404`: 不存在

### DELETE /api/data-sources/{id}
删除数据源（含 SQLite 表）

**响应** `200`: `{"message": "删除成功"}`

### POST /api/analysis
同步分析（供外部系统调用）

**请求**:
```json
{"question": "上月GMV?", "data_source_id": "xxx"}
```
**响应** `200`:
```json
{
  "final_response": "...",
  "charts": null,
  "tables": null,
  "execution_time": 2.35
}
```

### GET /api/sessions
历史会话列表

**响应** `200`: `[{session_id, title, message_count, created_at}]`

### GET /api/sessions/{id}
会话消息详情

**响应** `200`: `[{id, session_id, role, content, msg_type, created_at}]`

### DELETE /api/sessions/{id}
删除会话

**响应** `200`: `{"message": "删除成功"}`

## WebSocket 协议

**端点**: `ws://localhost:8000/ws/chat`

### 客户端 → 服务端

```json
{"type": "chat", "content": "上月GMV?", "data_source_id": "xxx"}
{"type": "human_approval", "check_id": "xxx", "result": "approved|rejected"}
```

### 服务端 → 客户端

| type | 说明 | 额外字段 |
|------|------|----------|
| planning | 规划完成 | steps[] |
| step_result | 步骤执行完成 | step_index, results[] |
| reflecting | 反思中 | retry_count, need_approval |
| human_checkpoint | 需要审批 | check_id, action, detail |
| approval_processed | 审批已处理 | check_id, result |
| responding | 生成回答中 | response_preview |
| done | 分析完成 | final_response, charts, tables |
| error | 错误 | message |

### GET /api/config
读取当前配置（API Key 脱敏）

**响应** `200`:
```json
{"provider": "deepseek", "model": "deepseek-chat", "api_key_masked": "sk-***abc"}
```

### POST /api/config
保存配置并持久化到 settings.yaml

**请求**:
```json
{"provider": "deepseek", "model": "deepseek-chat", "api_key": "sk-xxx"}
```
**响应** `200`: `{"message": "配置已保存"}`
