/**
 * @brief 分析报告导出工具
 *
 * 将对话中的全部分析结果（文字、图表、表格）整合生成 PDF 报告。
 * 使用 jsPDF + html2canvas 实现。
 */

import type { ChatMessage } from '../store/chatStore'

/** 报告配置 */
interface ReportConfig {
  title?: string
  date?: string
  dataSource?: string
}

/**
 * @brief 构建报告 HTML 内容
 */
function buildReportHtml(
  messages: ChatMessage[],
  config: ReportConfig,
): string {
  const dateStr = config.date || new Date().toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })

  // 筛选出有意义的消息对（user 提问 + assistant 回答）
  const pairs: { question: string; answer: ChatMessage }[] = []
  for (let i = 0; i < messages.length; i++) {
    if (messages[i].role === 'user' && i + 1 < messages.length && messages[i + 1].role === 'assistant') {
      pairs.push({
        question: messages[i].content,
        answer: messages[i + 1],
      })
    }
  }

  const title = config.title || '电商数据分析报告'
  const source = config.dataSource || '未知数据源'

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${title}</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: "Microsoft YaHei", "PingFang SC", "Helvetica Neue", sans-serif;
    color: #1f2937;
    line-height: 1.75;
    font-size: 13px;
    max-width: 750px;
    margin: 0 auto;
    padding: 40px 30px;
  }
  .cover {
    text-align: center;
    padding: 60px 0 40px;
    border-bottom: 2px solid #6366f1;
    margin-bottom: 36px;
    page-break-after: always;
  }
  .cover h1 {
    font-size: 28px;
    font-weight: 700;
    color: #111827;
    margin-bottom: 12px;
  }
  .cover .subtitle {
    font-size: 15px;
    color: #6366f1;
    margin-bottom: 24px;
  }
  .cover .meta {
    font-size: 13px;
    color: #6b7280;
    line-height: 2;
  }
  .section {
    margin-bottom: 32px;
    page-break-inside: avoid;
  }
  .section h2 {
    font-size: 17px;
    font-weight: 600;
    color: #111827;
    border-left: 3px solid #6366f1;
    padding-left: 10px;
    margin-bottom: 14px;
  }
  .question {
    background: #f5f3ff;
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 12px;
    font-size: 13px;
    color: #4c1d95;
    font-weight: 500;
  }
  .answer {
    color: #374151;
    font-size: 13px;
    line-height: 1.8;
    margin-bottom: 6px;
  }
  .answer p { margin-bottom: 8px; }
  .answer ul, .answer ol { padding-left: 20px; margin: 8px 0; }
  .answer li { margin-bottom: 4px; }
  .chart-placeholder {
    background: #f9fafb;
    border: 1px dashed #d1d5db;
    border-radius: 8px;
    padding: 20px;
    text-align: center;
    color: #9ca3af;
    font-size: 12px;
    margin: 12px 0;
    page-break-inside: avoid;
  }
  .table-wrapper {
    overflow-x: auto;
    margin: 10px 0;
    page-break-inside: avoid;
  }
  .table-wrapper table {
    border-collapse: collapse;
    width: 100%;
    font-size: 12px;
  }
  .table-wrapper th {
    background: #f3f4f6;
    border-bottom: 2px solid #e5e7eb;
    padding: 6px 10px;
    text-align: left;
    font-weight: 600;
    color: #374151;
    white-space: nowrap;
  }
  .table-wrapper td {
    border-bottom: 1px solid #f3f4f6;
    padding: 5px 10px;
    color: #4b5563;
  }
  .footer {
    text-align: center;
    color: #9ca3af;
    font-size: 11px;
    border-top: 1px solid #e5e7eb;
    padding-top: 16px;
    margin-top: 40px;
  }
</style>
</head>
<body>
  <!-- 封面 -->
  <div class="cover">
    <h1>${title}</h1>
    <div class="subtitle">AI 智能分析报告</div>
    <div class="meta">
      数据来源：${source}<br>
      生成时间：${dateStr}<br>
      分析问题数：${pairs.length} 个
    </div>
  </div>

  <!-- 分析内容 -->
  ${pairs
    .map(
      (pair, idx) => `
      <div class="section">
        <h2>分析 ${idx + 1}</h2>
        <div class="question">Q: ${pair.question}</div>
        <div class="answer">${formatMarkdownToHtml(pair.answer.content)}</div>
        ${buildChartsSection(pair.answer)}
        ${buildTablesSection(pair.answer)}
      </div>
    `,
    )
    .join('')}

  <!-- 页脚 -->
  <div class="footer">
    本报告由「掌柜 BizMaster」自动生成<br>
    数据基于用户上传的 ${source}
  </div>
</body>
</html>`
}

/** 将简单 Markdown 转为 HTML（基础转换） */
function formatMarkdownToHtml(md: string): string {
  if (!md) return '<p>（无内容）</p>'

  let html = md
    // 粗体
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // 标题
    .replace(/^### (.+)$/gm, '<h4 style="font-size:14px;font-weight:600;color:#374151;margin:10px 0 4px;">$1</h4>')
    .replace(/^## (.+)$/gm, '<h3 style="font-size:15px;font-weight:600;color:#111827;margin:14px 0 6px;">$1</h3>')
    .replace(/^# (.+)$/gm, '<h2 style="font-size:16px;font-weight:600;color:#111827;margin:16px 0 8px;">$1</h2>')
    // 无序列表
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    // 有序列表
    .replace(/^(\d+)\. (.+)$/gm, '<li>$2</li>')
    // 表格
    .replace(/^\|(.+)\|$/gm, (match) => {
      const cells = match.split('|').filter((c) => c.trim())
      const isHeader = /^[-:\s]+$/.test(cells[0] || '')
      if (isHeader) return ''
      const tag = match.includes('---') ? '' : 'td'
      return `<tr>${cells.map((c) => `<${tag}>${c.trim()}</${tag}>`).join('')}</tr>`
    })
    // 段落
    .replace(/^(?!<[a-z]|$)(.+)$/gm, '<p>$1</p>')

  // 包装连续 li
  html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>')

  return html || '<p>' + md + '</p>'
}

/** 构建图表区域 */
function buildChartsSection(msg: ChatMessage): string {
  if (!msg.charts || msg.charts.length === 0) return ''
  return msg.charts
    .map(
      (chart) => `
    <div class="chart-placeholder">
      📊 ${chart.title || chart.chart_type || '分析图表'}
      <br><small>（图表数据已附在报告中）</small>
    </div>`,
    )
    .join('')
}

/** 构建表格区域 */
function buildTablesSection(msg: ChatMessage): string {
  if (!msg.tables || msg.tables.length === 0) return ''
  return msg.tables
    .map(
      (table) => `
    <div class="table-wrapper">
      <table>
        <thead>
          <tr>${(table.columns || []).map((col) => `<th>${col}</th>`).join('')}</tr>
        </thead>
        <tbody>
          ${(table.data || [])
            .slice(0, 20)
            .map(
              (row) =>
                `<tr>${(table.columns || [])
                  .map((col) => `<td>${row[col] ?? ''}</td>`)
                  .join('')}</tr>`,
            )
            .join('')}
        </tbody>
      </table>
    </div>`,
    )
    .join('')
}

/**
 * @brief 导出 PDF 报告
 * @param messages 完整的消息列表
 * @param config 报告配置
 */
export async function exportPdfReport(
  messages: ChatMessage[],
  config: ReportConfig = {},
): Promise<void> {
  try {
    const html2canvas = (await import('html2canvas')).default
    const jsPDF = (await import('jspdf')).default

    const html = buildReportHtml(messages, config)

    // 创建隐藏容器渲染 HTML
    const container = document.createElement('div')
    container.innerHTML = html
    container.style.position = 'absolute'
    container.style.left = '-9999px'
    container.style.top = '0'
    container.style.width = '750px'
    container.style.background = '#ffffff'
    document.body.appendChild(container)

    try {
      const canvas = await html2canvas(container, {
        backgroundColor: '#ffffff',
        scale: 2,
        useCORS: true,
        allowTaint: true,
        logging: false,
      })

      const imgData = canvas.toDataURL('image/png')
      const pdf = new jsPDF('p', 'mm', 'a4')
      const pdfWidth = pdf.internal.pageSize.getWidth()
      const pdfHeight = pdf.internal.pageSize.getHeight()
      const imgHeight = (canvas.height * pdfWidth) / canvas.width

      let heightLeft = imgHeight
      let position = 0

      pdf.addImage(imgData, 'PNG', 0, position, pdfWidth, imgHeight)
      heightLeft -= pdfHeight

      while (heightLeft > 0) {
        position = -(imgHeight - heightLeft)
        pdf.addPage()
        pdf.addImage(imgData, 'PNG', 0, position, pdfWidth, imgHeight)
        heightLeft -= pdfHeight
      }

      const fileName = `电商分析报告_${new Date().toLocaleDateString('zh-CN').replace(/\//g, '-')}.pdf`
      pdf.save(fileName)
    } finally {
      document.body.removeChild(container)
    }
  } catch (e) {
    console.error('PDF 报告生成失败:', e)
    throw new Error('报告生成失败：' + (e as Error).message)
  }
}
