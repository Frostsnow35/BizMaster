# 掌柜 BizMaster 进阶升级规格说明

## 1. 背景与目标

本项目是面向中小电商商家的自助经营数据分析智能体，技术栈为 FastAPI + LangGraph + DeepSeek + React + Ant Design + ECharts。

本次进阶升级围绕三个诉求展开：

1. 让整个项目在前端界面与交互上显得更高级。
2. 在纯对话之外增加其他触发数据分析的方式。
3. 让分析成果更专业，涵盖图表、报告与 AI 分析角色。

目标产出是一个视觉统一、触发方式多样、分析成果可交付的进阶版本。

## 2. 需求决策

以下决策已经与用户确认，作为本次实现的依据。

1. 视觉方向：深色商务 BI 风。深蓝灰底色配金银质感，克制阴影，替换现有复古 CRT 扫描线与辉光元素。
2. 非对话触发方式：一键分析模板 + 定时自动报告。
3. AI 分析角色收敛为三个：数据分析师、电商运营专家、财务经营视角。
4. 报告交付：在线专业报告页 + 导出 PDF。

## 3. 现状核查

以下内容已经存在，无需重做，只做对齐与增强。

后端：

- 多角色定义模块 roles.py，当前为四个角色。
- 一键分析模板模块 templates.py，当前为九个模板。
- 报告与定时任务模型 models/report.py，含 ReportSchedule 与 Report。
- 报告生成服务 services/report_generator.py，运行 Agent 并落库报告。
- 定时调度服务 services/scheduler.py，基于 asyncio 循环扫描到期任务。
- 定时报告接口 api/schedules.py，含任务 CRUD、立即运行、报告列表与详情。
- 图表生成工具 tools/visualization.py，支持 line、bar、pie、scatter、treemap、indicator。

前端：

- 定时报告页 pages/SchedulePage.tsx，含定时任务与报告记录。
- 一键模板入口，位于 ChatContainer.tsx，拉取 /templates 并支持点击发起分析。
- 图表卡片 components/Chat/ChartCard.tsx，支持 ECharts 渲染与点击下钻。
- PDF 导出 utils/generateReport.ts，目前仅支持从对话导出。

## 4. 总体架构

```mermaid
flowchart TB
  subgraph 前端
    A[聊天/智能分析页] --> B[图表卡片渲染]
    A --> C[一键模板入口]
    D[定时报告页] --> E[报告记录列表]
    E --> F[专业报告详情页]
    F --> G[PDF 导出]
  end

  subgraph 后端API
    H[/chat 流式对话]
    I[/templates 模板]
    J[/schedules 定时]
    K[/reports 报告]
  end

  subgraph 服务层
    L[多角色分析引擎]
    M[报告生成服务]
    N[定时调度器]
  end

  subgraph 工具层
    O[数据查询]
    P[指标计算]
    Q[图表生成]
  end

  C --> I
  D --> J
  E --> K
  F --> K
  H --> L
  I --> L
  J --> N
  N --> M
  M --> L
  L --> Q
```

## 5. 阶段划分与验收标准

共七个阶段，按依赖顺序推进。每个阶段执行前先写该阶段的详细 spec。

1. 视觉商务 BI 化。统一深蓝灰底色与金银强调色，移除 CRT 扫描线与辉光，同步调整侧边栏、头部、图表卡片与定时报告页配色。验收：全局视觉统一为商务 BI 风，无残留复古元素。

2. 角色合并。把四个角色收敛为三个，新增电商运营专家并合并客户与营销角色，更新九个模板的角色归属，同步两处前端角色下拉。验收：前后端仅存在三个角色，模板与下拉一致。

3. 补齐 TypeScript 类型。在 types.ts 增加 ReportSchedule 与 AnalysisReport 接口。验收：前端 tsc 无类型错误。

4. 图表扩展。在 visualization.py 增加 funnel、radar、heatmap、waterfall 四种图表生成，确认前端可渲染。验收：八种以上图表能力可用，角色偏好引用的图表类型全部落地。

5. 专业报告页。新增报告详情路由与页面，从 /reports/{id} 拉取数据，用 ECharts 渲染图表、表格渲染数据、按章节组织结论。验收：报告可在独立页面完整浏览。

6. 报告 PDF 导出。改造 generateReport 逻辑，支持从已保存报告导出 PDF。验收：报告详情页可下载 PDF。

7. 全量验证。启动后端、运行 pytest、执行前端 tsc 与 build，修复错误。验收：后端可启动、测试通过、前端构建成功。

## 6. 技术规范约束

1. 变量与函数使用 snake_case，类使用 PascalCase，常量使用 UPPER_CASE。
2. 函数头注释包含 @brief、@param、@return、@throws、@example。
3. 单文件不超过 500 行，接口定义与实现分离。
4. 代码通过 ESLint 与 Prettier 校验。
5. 减少多 Agent 并行开发，优先在主对话中执行。
