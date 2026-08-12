# 电商经营数据分析智能体

面向中小电商商家的自助经营数据分析工具，支持自然语言对话式数据分析。

## 快速启动

### 1. 安装依赖

```bash
# 后端
cd backend
pip install -r requirements.txt

# 前端
cd frontend
npm install
```

### 2. 配置 API Key

编辑 `backend/config/settings.yaml`，填入 DeepSeek API Key：
```yaml
deepseek:
  api_key: "sk-your-key"
```

或在启动后的设置页面填写（推荐）。

### 3. 启动

```bash
# 终端 1：启动后端
cd backend
python -m uvicorn app.main:app --reload --port 8000

# 终端 2：启动前端
cd frontend
npm run dev
```

### 4. 使用

1. 浏览器打开 `http://localhost:5173`
2. 进入「系统设置」配置 DeepSeek API Key
3. 进入「数据管理」上传 CSV/Excel 数据文件
4. 进入「智能分析」选择数据源，输入分析问题

## 示例问题

```
本月总销售额（GMV）是多少？
各商品类别的销售额排名 TOP 10
上个月每天的订单量变化趋势
售价和销量的关系是什么？
```

## 技术栈

| 层 | 技术 |
|------|------|
| 前端 | React + Vite + Ant Design + ECharts |
| 后端 | FastAPI + LangGraph |
| LLM | DeepSeek API |
| 数据 | SQLite + Pandas |
| 打包 | PyInstaller + Electron |

## 项目结构

```
ecommerce-data-agent/
├── backend/
│   ├── app/
│   │   ├── api/           # REST + WebSocket 端点
│   │   ├── agent/         # LangGraph 状态图引擎
│   │   │   ├── nodes/     # 六大节点
│   │   │   ├── tools/     # 三大分析工具
│   │   │   └── prompts/   # LLM 提示词
│   │   ├── core/          # 基础设施（配置/数据库/LLM）
│   │   ├── models/        # ORM 模型
│   │   ├── services/      # 业务逻辑
│   │   └── llm_providers/ # LLM 适配层
│   ├── config/            # YAML 配置文件
│   └── tests/             # 单元测试（25 个）
├── frontend/
│   └── src/
│       ├── components/    # Chat / DataUpload / Layout
│       ├── pages/         # ChatPage / DataManage / Settings
│       ├── hooks/         # useChat / useDataSources
│       ├── store/         # Zustand 状态管理
│       └── styles/        # 全局主题样式
└── docs/                  # 设计文档
```

## 版本

v0.1.0 - MVP 完成，五轮审查通过
