import ReactMarkdown from 'react-markdown'
import { Collapse, Typography, Dropdown, message as antdMessage, Popconfirm } from 'antd'
import type { MenuProps } from 'antd'
import {
  LoadingOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  BulbOutlined,
  SearchOutlined,
  SyncOutlined,
  DownloadOutlined,
  FileMarkdownOutlined,
  FileImageOutlined,
  FilePdfOutlined,
  ExclamationCircleOutlined,
  CopyOutlined,
  DeleteOutlined,
} from '@ant-design/icons'
import type { ChatMessage, ThinkingStep, OutputFormat } from '../../store/chatStore'
import { useChatStore } from '../../store/chatStore'
import { translateError } from '../../utils/errorMessages'
import FeedbackButtons from './FeedbackButtons'
import client from '../../api/client'
import ChartCard from './ChartCard'
import TableCard from './TableCard'

const { Text } = Typography

/* ── 全局样式注入（一次性） ── */
const styleId = 'mb-keyframes'
if (typeof document !== 'undefined' && !document.getElementById(styleId)) {
  const el = document.createElement('style')
  el.id = styleId
  el.textContent = `
    @keyframes mb-pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
    @keyframes mb-blink { 0%,100%{opacity:1} 50%{opacity:0} }
    @keyframes mb-fadeIn { from{opacity:0;transform:translateY(6px)} to{opacity:1;transform:translateY(0)} }
    .mb-msg-enter { animation: mb-fadeIn 0.35s ease-out; }
    .mb-pulse { animation: mb-pulse 1.4s ease-in-out infinite; }
    .mb-blink { animation: mb-blink 1s step-end infinite; }
  `
  document.head.appendChild(el)
}

/* 思考步骤配置 */
const stepConfig: Record<string, { icon: React.ReactNode; label: string }> = {
  planning:  { icon: <BulbOutlined />,        label: '规划' },
  step_result:{ icon: <CheckCircleOutlined />,label: '执行' },
  reflecting: { icon: <SearchOutlined />,      label: '校验' },
  responding: { icon: <LoadingOutlined />,     label: '生成' },
}

/* 单条思考步骤 */
function ThinkingStepItem({ step, isLast }: { step: ThinkingStep; isLast: boolean }) {
  const cfg = stepConfig[step.type] || stepConfig.reflecting
  const isSuccess = (step.successCount ?? step.totalCount ?? 0) >= (step.totalCount ?? 1)
  const icon = step.type === 'step_result' && !isSuccess
    ? <CloseCircleOutlined style={{ color: '#ef4444' }} />
    : cfg.icon

  return (
    <div style={{
      display: 'flex', gap: 8, padding: '3px 0', fontSize: 12, color: '#5b6674',
      borderLeft: isLast ? '2px solid transparent' : '2px solid #243040',
      marginLeft: 6, paddingLeft: 10, paddingBottom: isLast ? 0 : 4,
      transition: 'color 0.2s',
    }}>
      <span style={{ marginTop: 1, color: isSuccess ? '#34d399' : '#5b6674' }}>{icon}</span>
      <div style={{ flex: 1, lineHeight: '18px' }}>
        <span style={{ color: '#8b96a3', marginRight: 5, fontSize: 11 }}>{cfg.label}</span>
        <span style={{ color: '#8b96a3' }}>{step.content}</span>
      </div>
    </div>
  )
}

/* 思考过程折叠面板 */
function ThinkingPanel({ steps, expanded }: { steps: ThinkingStep[]; expanded: boolean }) {
  if (!steps || steps.length === 0) return null

  return (
    <Collapse
      ghost
      size="small"
      activeKey={expanded ? ['thinking'] : []}
      items={[{
        key: 'thinking',
        label: (
          <span style={{ fontSize: 12, color: '#5b6674', display: 'flex', alignItems: 'center', gap: 6 }}>
            <SyncOutlined spin={!expanded} style={{ fontSize: 11 }} />
            <span>思考过程</span>
            <span style={{
              background: '#1a2330', color: '#8b96a3', fontSize: 10,
              padding: '1px 6px', borderRadius: 10, fontWeight: 500,
            }}>
              {steps.length} 步
            </span>
          </span>
        ),
        children: (
          <div style={{ padding: '0' }}>
            {steps.map((step, i) => (
              <ThinkingStepItem key={i} step={step} isLast={i === steps.length - 1} />
            ))}
          </div>
        ),
        styles: {
          header: { padding: '2px 0', fontSize: 12 },
          body: { padding: '2px 0 0' },
        },
      }]}
      style={{
        background: 'transparent',
        marginBottom: 8,
        border: '1px solid #1a2330',
        borderRadius: 6,
        padding: '4px 12px',
      }}
    />
  )
}

interface Props {
  message: ChatMessage
  onChartDrilldown?: (params: { category: string; value: number; chartType: string; title?: string }) => void
}

/* 输出格式选项 */
const FORMAT_OPTIONS: { key: string; label: string }[] = [
  { key: 'bullet', label: '要点' },
  { key: 'table',  label: '表格' },
  { key: 'report', label: '报告' },
  { key: 'chart',  label: '图表' },
]

/**
 * @brief 删除所有 Markdown 表格行（以 | 开头、以 | 结尾的整行）
 * 支持行首空格缩进、行尾无换行符等边界情况
 */
function stripTableLines(text: string): string {
  return text
    .split('\n')
    .filter(line => !/^\s*\|.*\|\s*$/.test(line))
    .join('\n')
}

/**
 * @brief 根据选中的格式过滤 Markdown 内容
 * 确保点击按钮后只展示该格式对应的内容
 */
function formatFilterContent(content: string, format: string): string {
  if (!content || format === 'report') return content  // report 展示全部

  if (format === 'bullet') {
    let filtered = stripTableLines(content)
    filtered = filtered.replace(/^#{1,3}\s+[^\n]*\n?/gm, '')
    filtered = filtered.replace(/\n{3,}/g, '\n\n')
    return filtered.trim()
  }

  if (format === 'table') {
    const tableLines = content.split('\n').filter(line => /^\s*\|.*\|\s*$/.test(line))
    if (tableLines.length >= 2) {
      return tableLines.join('\n')
    }
    const lines = content.split('\n')
      .filter(l => l.trim() && !l.trim().startsWith('#') && !l.trim().startsWith('- ') && !l.trim().startsWith('|'))
      .slice(0, 3)
    return lines.join('\n')
  }

  if (format === 'chart') {
    let filtered = stripTableLines(content)
    filtered = filtered.replace(/^#{1,3}\s+[^\n]*\n?/gm, '')
    const lines = filtered.split('\n').map(l => l.trim()).filter(Boolean).slice(0, 8)
    return lines.join('\n')
  }

  return content
}

/* ── 加载动画：三个跳动圆点 ── */
function LoadingDots() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 0' }}>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="mb-pulse"
          style={{
            width: 7, height: 7, borderRadius: '50%',
            background: '#60a5fa',
            animationDelay: `${i * 0.2}s`,
          }}
        />
      ))}
      <span style={{ fontSize: 13, color: '#5b6674', marginLeft: 4 }}>分析中...</span>
    </div>
  )
}

function MessageBubble({ message, onChartDrilldown }: Props) {
  const isUser = message.role === 'user'
  const isStreaming = message.isStreaming
  const hasThinking = (message.thinkingSteps?.length ?? 0) > 0

  /* ── 用户消息 ── */
  if (isUser) {
    const handleCopy = async () => {
      try {
        await navigator.clipboard.writeText(message.content)
        antdMessage.success('已复制到剪贴板')
      } catch {
        antdMessage.error('复制失败')
      }
    }

    const handleDelete = async () => {
      const store = useChatStore.getState()
      const sessionId = store.currentSessionId

      if (message.recordId && sessionId) {
        try {
          await client.delete(`/sessions/${sessionId}/messages/${message.recordId}`)
        } catch {
          // 后端删除失败不影响前端
        }
      }

      const msgs = store.messages
      const idx = msgs.findIndex((m) => m.id === message.id)
      if (idx !== -1 && idx + 1 < msgs.length) {
        const nextMsg = msgs[idx + 1]
        if (nextMsg.role === 'assistant') {
          store.removeMessage(nextMsg.id)
        }
      }
      store.removeMessage(message.id)
    }

    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }} className="mb-msg-enter">
        <div style={{
          maxWidth: '72%',
          padding: '10px 18px',
          borderRadius: '6px 6px 0 6px',
          background: 'linear-gradient(135deg, #2563eb, #3b82f6)',
          color: '#ffffff',
          wordBreak: 'break-word',
          boxShadow: '0 0 10px rgba(59,130,246,0.25)',
          fontSize: 14,
          lineHeight: 1.6,
        }}>
          {message.content}
        </div>
        {/* 操作按钮 */}
        <div style={{ display: 'flex', gap: 2, marginTop: 4, opacity: 0.7 }}>
          <span
            onClick={handleCopy}
            style={{
              cursor: 'pointer', padding: '2px 6px', borderRadius: 4,
              fontSize: 12, color: '#5b6674', transition: 'color 0.15s',
            }}
            title="复制"
            onMouseEnter={(e) => { e.currentTarget.style.color = '#60a5fa' }}
            onMouseLeave={(e) => { e.currentTarget.style.color = '#5b6674' }}
          >
            <CopyOutlined />
          </span>
          <Popconfirm
            title="确认删除"
            description="删除后将同时移除本条消息和 AI 回复"
            onConfirm={handleDelete}
            okText="确认"
            cancelText="取消"
          >
            <span
              style={{
                cursor: 'pointer', padding: '2px 6px', borderRadius: 4,
                fontSize: 12, color: '#5b6674', transition: 'color 0.15s',
              }}
              title="删除"
              onMouseEnter={(e) => { e.currentTarget.style.color = '#ef4444' }}
              onMouseLeave={(e) => { e.currentTarget.style.color = '#5b6674' }}
            >
              <DeleteOutlined />
            </span>
          </Popconfirm>
        </div>
      </div>
    )
  }

  /* ── 错误消息 ── */
  if (message.msgType === 'error') {
    const friendly = translateError(message.content)

    return (
      <div style={{ maxWidth: '85%' }} className="mb-msg-enter">
        <div style={{
          padding: '16px 20px',
          borderRadius: 6,
          background: '#1a1114',
          border: '1px solid #3a2028',
          wordBreak: 'break-word',
        }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginBottom: friendly ? 10 : 0 }}>
            <ExclamationCircleOutlined style={{ color: '#ef4444', marginTop: 2, fontSize: 14 }} />
            <div style={{ flex: 1 }}>
              <Text strong style={{ color: '#ef4444', fontSize: 14 }}>
                {friendly?.title || '分析过程出错'}
              </Text>
              <div style={{ color: '#d5a5ae', fontSize: 13, lineHeight: 1.7, marginTop: 6 }}>
                {friendly ? (
                  <>
                    <p style={{ margin: '0 0 8px' }}>{friendly.description}</p>
                    <div style={{ fontSize: 12, color: '#c08089', marginTop: 4 }}>
                      <div style={{ fontWeight: 500, marginBottom: 4 }}>您可以：</div>
                      {friendly.suggestions.map((s, i) => (
                        <div key={i} style={{ paddingLeft: 8, marginBottom: 2 }}>
                          {i + 1}. {s}
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <div style={{ whiteSpace: 'pre-wrap' }}>{message.content}</div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  /* ── 当前选中格式 ── */
  const currentFormat = message.format || 'bullet'

  /* ── AI 回答 ── */
  return (
    <div style={{ maxWidth: '85%' }} className="mb-msg-enter">
      {/* 思考面板 */}
      {hasThinking && (
        <ThinkingPanel
          steps={message.thinkingSteps!}
          expanded={message.thinkingExpanded ?? false}
        />
      )}

      {/* 回答卡片：要点/图表/表格格式时显示，报告格式时隐藏（避免与报告面板重复） */}
      {currentFormat !== 'report' && (
      <div id={`msg-bubble-${message.id}`} style={{
        padding: '16px 20px',
        borderRadius: 6,
        background: '#111826',
        border: '1px solid #243040',
        boxShadow: '0 0 0 1px rgba(59,130,246,0.06)',
        wordBreak: 'break-word',
        lineHeight: 1.75,
        transition: 'box-shadow 0.2s',
      }}>
        {/* 流式加载 */}
        {isStreaming && !message.content && <LoadingDots />}

        {/* Markdown 正文：始终显示要点格式（过滤掉表格和标题） */}
        {message.content && (
          <div style={{ fontSize: 14, color: '#d5dbe3' }}>
            <ReactMarkdown
              components={{
                table: ({ children }) => (
                  <div style={{ overflowX: 'auto', margin: '12px 0' }}>
                    <table style={{
                      borderCollapse: 'collapse', width: '100%', fontSize: 13,
                    }}>
                      {children}
                    </table>
                  </div>
                ),
                th: ({ children }) => (
                  <th style={{
                    borderBottom: '2px solid #243040', padding: '8px 12px',
                    textAlign: 'left', fontWeight: 600, color: '#8b96a3',
                    background: '#16233a',
                  }}>
                    {children}
                  </th>
                ),
                td: ({ children }) => (
                  <td style={{
                    borderBottom: '1px solid #243040', padding: '8px 12px',
                    color: '#d5dbe3',
                  }}>
                    {children}
                  </td>
                ),
                h2: ({ children }) => (
                  <h2 style={{ fontSize: 16, fontWeight: 600, color: '#60a5fa', margin: '16px 0 8px' }}>
                    {children}
                  </h2>
                ),
                h3: ({ children }) => (
                  <h3 style={{ fontSize: 14, fontWeight: 600, color: '#8b96a3', margin: '12px 0 6px' }}>
                    {children}
                  </h3>
                ),
                ul: ({ children }) => (
                  <ul style={{ paddingLeft: 20, margin: '6px 0' }}>{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol style={{ paddingLeft: 20, margin: '6px 0' }}>{children}</ol>
                ),
                li: ({ children }) => (
                  <li style={{ marginBottom: 4, color: '#d5dbe3' }}>{children}</li>
                ),
                code: ({ className, children, ...props }: any) => {
                  const isInline = !className
                  return isInline ? (
                    <code style={{
                      background: '#1a2330', color: '#d4af37', padding: '1px 5px',
                      borderRadius: 4, fontSize: '0.9em',
                    }} {...props}>{children}</code>
                  ) : (
                    <code style={{
                      display: 'block', background: '#0b0f14', color: '#60a5fa',
                      padding: '12px 16px', borderRadius: 6, fontSize: 13,
                      overflowX: 'auto', margin: '8px 0',
                    }} {...props}>{children}</code>
                  )
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        )}

        {/* 流式光标 */}
        {isStreaming && message.content && (
          <span className="mb-blink" style={{
            display: 'inline-block', width: 7, height: 16, borderRadius: 1,
            background: '#60a5fa', marginLeft: 2, verticalAlign: 'text-bottom',
          }} />
        )}

        {/* 底部工具栏：导出 + 格式切换 */}
        {!isStreaming && message.content && (
          <div style={{
            marginTop: 14,
            borderTop: '1px solid #243040',
            paddingTop: 10,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 8,
          }}>
            {/* 导出下拉菜单 */}
            <Dropdown
              menu={{
                items: [
                  {
                    key: 'md',
                    icon: <FileMarkdownOutlined />,
                    label: '导出 Markdown',
                    onClick: () => {
                      const displayContent = message.content
                      const blob = new Blob([displayContent], { type: 'text/markdown' })
                      const url = URL.createObjectURL(blob)
                      const a = document.createElement('a')
                      a.href = url; a.download = `分析报告_${new Date().toLocaleDateString()}.md`
                      a.click(); URL.revokeObjectURL(url)
                    },
                  },
                  {
                    key: 'image',
                    icon: <FileImageOutlined />,
                    label: '导出图片',
                    onClick: async () => {
                      try {
                        const bubble = document.getElementById(`msg-bubble-${message.id}`)
                        if (!bubble) { alert('无法找到消息内容，请刷新后重试'); return }
                        const html2canvas = (await import('html2canvas')).default
                        const canvas = await html2canvas(bubble, { backgroundColor: '#111826', scale: 2, useCORS: true, allowTaint: true })
                        canvas.toBlob((blob) => {
                          if (!blob) { alert('图片生成失败'); return }
                          const url = URL.createObjectURL(blob)
                          const a = document.createElement('a')
                          a.href = url; a.download = `分析报告_${new Date().toLocaleDateString()}.png`
                          a.click(); URL.revokeObjectURL(url)
                        }, 'image/png')
                      } catch (e) { alert('导出图片需要安装 html2canvas 依赖') }
                    },
                  },
                  {
                    key: 'pdf',
                    icon: <FilePdfOutlined />,
                    label: '导出 PDF',
                    onClick: async () => {
                      try {
                        const bubble = document.getElementById(`msg-bubble-${message.id}`)
                        if (!bubble) { alert('无法找到消息内容，请刷新后重试'); return }
                        const html2canvas = (await import('html2canvas')).default
                        const jsPDF = (await import('jspdf')).default
                        const canvas = await html2canvas(bubble, { backgroundColor: '#ffffff', scale: 2, useCORS: true, allowTaint: true })
                        const imgData = canvas.toDataURL('image/png')
                        const pdf = new jsPDF('p', 'mm', 'a4')
                        const pw = pdf.internal.pageSize.getWidth()
                        const ph = (canvas.height * pw) / canvas.width
                        pdf.addImage(imgData, 'PNG', 0, 0, pw, ph)
                        if (ph > pdf.internal.pageSize.getHeight()) {
                          let pos = 0
                          while (ph + pos > 0) {
                            pdf.addPage(); pos -= pdf.internal.pageSize.getHeight()
                            pdf.addImage(imgData, 'PNG', 0, pos, pw, ph)
                          }
                        }
                        pdf.save(`分析报告_${new Date().toLocaleDateString()}.pdf`)
                      } catch (e) { alert('导出 PDF 需要安装 html2canvas 和 jspdf 依赖') }
                    },
                  },
                ] as MenuProps['items'],
              }}
              trigger={['click']}
            >
              <button style={{
                border: '1px solid #243040', background: '#111826', color: '#8b96a3',
                fontSize: 11, padding: '3px 10px', borderRadius: 4, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 4, transition: 'all 0.15s',
              }}>
                <DownloadOutlined style={{ fontSize: 11 }} />导出
              </button>
            </Dropdown>

            {/* 格式切换按钮组：始终可点击，缺数据时显示兜底内容 */}
            <div style={{ display: 'flex', gap: 4, background: '#16233a', borderRadius: 4, padding: 2 }}>
              {FORMAT_OPTIONS.map((opt) => {
                const isActive = currentFormat === opt.key

                return (
                  <button
                    key={opt.key}
                    onClick={() => {
                      useChatStore.getState().updateMessage(message.id, {
                        format: opt.key as OutputFormat,
                      })
                    }}
                    style={{
                      border: 'none',
                      background: isActive ? '#3b82f6' : 'transparent',
                      color: isActive ? '#ffffff' : '#5b6674',
                      fontSize: 12, padding: '4px 12px', borderRadius: 4,
                      cursor: 'pointer',
                      fontWeight: isActive ? 600 : 400,
                      boxShadow: isActive ? '0 0 8px rgba(59,130,246,0.35)' : 'none',
                      transition: 'all 0.15s',
                    }}
                    title={`切换为${opt.label}格式`}
                  >
                    {opt.label}
                  </button>
                )
              })}
            </div>
          </div>
        )}
      </div>
      )}

      {/* ── 展示区域：根据选中格式显示对应内容 ── */}

      {/* 图表：选中「图表」时显示，无图表数据时显示兜底 */}
      {currentFormat === 'chart' && (
        <div style={{ marginTop: 12 }}>
          {(message.charts?.length ?? 0) > 0 ? (
            message.charts!.map((chart, idx) => (
              <ChartCard
                key={idx}
                option={chart.echarts_option}
                title={chart.title}
                onDrilldown={onChartDrilldown ? (params) => onChartDrilldown({
                  ...params,
                  title: chart.title || chart.chart_type,
                }) : undefined}
              />
            ))
          ) : (
            <FallbackFormatCard icon="📊" text="该分析结果未包含图表数据，请查看「要点」或「报告」格式获取分析结论" />
          )}
        </div>
      )}

      {/* 表格：选中「表格」时显示，无表格数据时尝试解析 Markdown 表格 */}
      {currentFormat === 'table' && (
        <div style={{ marginTop: 12 }}>
          {(message.tables?.length ?? 0) > 0 ? (
            message.tables!.map((table, idx) => (
              <TableCard key={idx} data={table.data} columns={table.columns} />
            ))
          ) : (
            <FallbackTableFromMarkdown content={message.content} />
          )}
        </div>
      )}

      {/* 报告：选中「报告」时显示，优先 formatVariants，回退显示原文 */}
      {currentFormat === 'report' && (
        <div style={{
          marginTop: 12, padding: '16px 20px', borderRadius: 6,
          background: '#111826', border: '1px solid #243040',
          boxShadow: '0 0 0 1px rgba(59,130,246,0.06)',
          fontSize: 14, color: '#d5dbe3', lineHeight: 1.75,
        }}>
          {message.formatVariants?.report ? (
            <ReactMarkdown components={reportComponents}>{message.formatVariants.report}</ReactMarkdown>
          ) : (
            <FallbackReportContent content={message.content} />
          )}
        </div>
      )}
      {/* 用户反馈：仅 AI 回答、非错误、非流式时显示 */}
      {message.role === 'assistant' && !message.isStreaming && (
        <FeedbackButtons messageId={message.id} />
      )}
    </div>
  )
}

/* ── 兜底组件定义 ── */

/** Markdown 渲染组件（复用于报告格式） */
const reportComponents = {
  h2: ({ children }: any) => <h2 style={{ fontSize: 16, fontWeight: 600, color: '#60a5fa', margin: '16px 0 8px' }}>{children}</h2>,
  h3: ({ children }: any) => <h3 style={{ fontSize: 14, fontWeight: 600, color: '#8b96a3', margin: '12px 0 6px' }}>{children}</h3>,
  ul: ({ children }: any) => <ul style={{ paddingLeft: 20, margin: '6px 0' }}>{children}</ul>,
  li: ({ children }: any) => <li style={{ marginBottom: 4, color: '#d5dbe3' }}>{children}</li>,
  table: ({ children }: any) => (
    <div style={{ overflowX: 'auto', margin: '12px 0' }}>
      <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: 13 }}>{children}</table>
    </div>
  ),
  th: ({ children }: any) => <th style={{ borderBottom: '2px solid #243040', padding: '8px 12px', textAlign: 'left', fontWeight: 600, color: '#8b96a3', background: '#16233a' }}>{children}</th>,
  td: ({ children }: any) => <td style={{ borderBottom: '1px solid #243040', padding: '8px 12px', color: '#d5dbe3' }}>{children}</td>,
}

/** 格式缺数据时的兜底提示卡片 */
function FallbackFormatCard({ icon, text }: { icon: string; text: string }) {
  return (
    <div style={{
      padding: '28px 20px', borderRadius: 6,
      background: '#111826', border: '1px dashed #243040',
      textAlign: 'center', color: '#5b6674', fontSize: 13,
    }}>
      <div style={{ fontSize: 32, marginBottom: 8 }}>{icon}</div>
      <div>{text}</div>
    </div>
  )
}

/** 表格兜底：尝试从 Markdown 内容中提取表格行渲染 */
function FallbackTableFromMarkdown({ content }: { content: string }) {
  if (!content) {
    return <FallbackFormatCard icon="📋" text="该分析结果未包含表格数据" />
  }

  const lines = content.split('\n')
  const tableLines = lines.filter((l) => /^\s*\|.*\|\s*$/.test(l.trim()))

  if (tableLines.length < 2) {
    const dataLines = lines.filter((l) => {
      const t = l.trim()
      return t && !t.startsWith('#') && !t.startsWith('-') && t.includes(',') && !t.startsWith('|')
    })
    if (dataLines.length === 0) {
      return <FallbackFormatCard icon="📋" text="该分析结果未包含表格数据，请查看「要点」格式" />
    }
    return (
      <div style={{
        padding: '12px 16px', borderRadius: 6,
        background: '#111826', border: '1px solid #243040',
        fontSize: 12, color: '#8b96a3', whiteSpace: 'pre-wrap',
        fontFamily: 'monospace',
      }}>
        {dataLines.join('\n')}
      </div>
    )
  }

  return (
    <div style={{ overflowX: 'auto', padding: '4px 0' }}>
      <table style={{
        borderCollapse: 'collapse', width: '100%', fontSize: 12,
        background: '#111826', borderRadius: 6, overflow: 'hidden',
        border: '1px solid #243040',
      }}>
        <tbody>
          {tableLines.map((line, i) => {
            const cells = line.split('|').filter((c) => c.trim())
            const isSep = cells.every((c) => /^[-:\s]+$/.test(c.trim()))
            if (isSep) return null
            const CellTag = i === 0 ? 'th' : 'td'
            return (
              <tr key={i} style={{ borderBottom: i === 0 ? '2px solid #243040' : '1px solid #243040' }}>
                {cells.map((cell, j) => (
                  <CellTag
                    key={j}
                    style={{
                      padding: '6px 10px',
                      textAlign: 'left',
                      fontWeight: i === 0 ? 600 : 400,
                      color: i === 0 ? '#8b96a3' : '#d5dbe3',
                      background: i === 0 ? '#16233a' : 'transparent',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {cell.trim()}
                  </CellTag>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

/** 报告兜底：显示 Markdown 渲染的原文 */
function FallbackReportContent({ content }: { content: string }) {
  if (!content) {
    return <FallbackFormatCard icon="📄" text="该分析结果未包含报告格式内容" />
  }
  return <ReactMarkdown components={reportComponents}>{content}</ReactMarkdown>
}

export default MessageBubble
