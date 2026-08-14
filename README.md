# 掌柜 BizMaster

面向中小电商商家的**经营数据分析智能体**：上传数据后，用自然语言提问即可获得销售分析、客户洞察、库存诊断与可视化报告，无需 SQL 和表格技能。

[![Release](https://img.shields.io/github/v/release/Frostsnow35/BizMaster)](https://github.com/Frostsnow35/BizMaster/releases)

## 下载安装包

前往 [GitHub Releases](https://github.com/Frostsnow35/BizMaster/releases/latest) 下载 Windows 安装包：

| 文件 | 说明 |
|------|------|
| `BizMaster-<版本>.exe` | NSIS 安装包（推荐），向导式安装 |
| `BizMaster-<版本>.zip` | 免安装压缩包，解压即用 |

> 未购买商业代码签名证书，Windows SmartScreen 可能提示"未知发布者"，选择"仍要运行"即可。

## 功能

- 自然语言对话式数据分析，支持**下钻追问**
- 多数据源管理：CSV / Excel 上传，示例数据一键导入，主数据源 + 关联数据源联合分析
- 四种输出格式：要点 / 表格 / 深度报告 / 图表
- 分析模板一键复用，PDF 报告导出
- 图表下钻、点赞踩反馈、消息复制与撤回
- 本地数据存储（SQLite），API Key 加密保存

## 快速启动（开发模式）

```bash
# 后端
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev
```

浏览器打开 `http://localhost:5173`，进入「系统设置」配置 DeepSeek API Key，再进入「数据管理」上传数据即可开始分析。

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
| 数据 | SQLite + Pandas + DuckDB |
| 打包 | PyInstaller + Electron + electron-builder |

## 项目结构

```
├── backend/
│   ├── app/
│   │   ├── api/           # REST + WebSocket 端点
│   │   ├── agent/         # LangGraph 状态图引擎
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
├── electron/              # 桌面端封装（主进程/托盘/自动拉起后端）
├── sample-data/           # 示例数据
├── scripts/               # 开发与构建脚本
└── docs/                  # 设计文档
```

## 桌面版构建

本地构建（Windows）：

```bat
scripts\build.bat
```

GitHub Actions 自动构建：推送 `v*` 标签（如 `v0.1.0`）即触发，产物自动上传到 Release。

```bash
git tag v0.1.0
git push origin v0.1.0
```

## 版本

v0.1.1 - 字段映射确认、AI 未接入引导、预测置信区间、报告失败重试与调度器可靠性优化
v0.1.0 - MVP 完成，五轮审查通过，桌面打包与发布就绪
