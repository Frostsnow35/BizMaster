# 阶段六 spec：报告 PDF 导出

## 目标

在报告详情页提供「导出 PDF」，从已保存报告（AnalysisReport）生成可交付的 PDF 文件。

## 现状

1. frontend/src/utils/generateReport.ts 已有 exportPdfReport(messages)，仅支持从对话消息导出。
2. 报告详情页 ReportDetailPage 尚无导出入口。
3. 已有 html2canvas + jsPDF 依赖，Markdown 转 HTML、表格渲染逻辑可复用。

## 改动范围

1. generateReport.ts：新增 exportReportPdf(report)，构建单报告专业 HTML（封面、元信息、summary、图表标注、表格），复用 html2canvas + jsPDF 导出。
2. 抽取 renderHtmlToPdf 公共函数，供对话导出与报告导出共用。
3. ReportDetailPage.tsx：新增「导出 PDF」按钮，调用 exportReportPdf。

## 验收标准

1. 报告详情页可点击导出 PDF，生成包含标题、元信息、文字结论、图表标注、数据明细的 PDF。
2. 对话导出（exportPdfReport）行为不变。
3. 前端 tsc --noEmit 通过。
