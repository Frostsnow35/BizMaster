import { useRef, useEffect, useState, useMemo, useCallback } from 'react'
import { Input, Button, Select, Tooltip, Tag, Modal, Checkbox, Typography, Space, message, Dropdown } from 'antd'
import { SendOutlined, ThunderboltOutlined, DownloadOutlined, InfoCircleOutlined, ExclamationCircleOutlined, CloseOutlined, FilePdfOutlined, StarOutlined, StarFilled } from '@ant-design/icons'
import MessageBubble from './MessageBubble'
import ApprovalModal from '../HumanCheckpoint/ApprovalModal'
import OnboardingGuide from './OnboardingGuide'
import { useChat } from '../../hooks/useChat'
import { useAnalysisTemplates } from '../../hooks/useAnalysisTemplates'
import client from '../../api/client'
import type { DataSourceInfo, PresetTemplate } from '../../api/types'
import type { TableCandidate } from '../../store/chatStore'
import { useChatStore } from '../../store/chatStore'
import { exportPdfReport } from '../../utils/generateReport'

const { TextArea } = Input
const { Text, Paragraph } = Typography

/* 分析角色选项（自动匹配 + 三个专业分析师） */
const ROLE_OPTIONS = [
  { value: 'auto', label: '自动匹配角色' },
  { value: 'data_analyst', label: '数据分析师' },
  { value: 'operations_analyst', label: '电商运营专家' },
  { value: 'finance_analyst', label: '财务经营分析师' },
]

interface Props {
  dataSources: DataSourceInfo[]
  prefilledDsId?: string
  prefilledQuestion?: string
}

/* 根据数据源类型生成推荐分析问题 */
function suggestQuestions(name: string, cols: { name: string; dtype: string }[]): string[] {
  const all = (name + ' ' + cols.map((c) => c.name).join(' ')).toLowerCase()
  const suggestions: string[] = []
  const isOrder = all.includes('order') || all.includes('订单') || all.includes('销售') || all.includes('实付') || all.includes('支付')
  const isCustomer = all.includes('customer') || all.includes('客户') || all.includes('会员') || all.includes('用户')
  const isProduct = all.includes('product') || all.includes('商品') || all.includes('类目') || all.includes('品类') || all.includes('sku')

  if (isOrder && (all.includes('金额') || all.includes('price') || all.includes('amount') || all.includes('total') || all.includes('数量'))) {
    suggestions.push('本月销售额趋势如何？')
    suggestions.push('各品类销售额占比是多少？')
  }
  if (isOrder && (all.includes('日期') || all.includes('date') || all.includes('time') || all.includes('下单'))) {
    suggestions.push('最近30天每日订单量是多少？')
  }
  if (isCustomer) {
    suggestions.push('客户画像分析（消费能力/地域分布）')
  }
  if (isProduct && !isOrder) {
    suggestions.push('有哪些商品品类？数量分布如何？')
  }
  if (suggestions.length === 0) {
    suggestions.push('帮我预览一下数据')
    suggestions.push('数据中有哪些主要字段？')
  }
  return suggestions.slice(0, 3)
}

function ChatContainer({ dataSources, prefilledDsId, prefilledQuestion }: Props) {
  const [inputValue, setInputValue] = useState(prefilledQuestion || '')
  const [selectedDsIds, setSelectedDsIds] = useState<string[]>(prefilledDsId ? [prefilledDsId] : [])
  const [role, setRole] = useState<string>('auto')
  const [presets, setPresets] = useState<PresetTemplate[]>([])
  const [onboardingDataSources, setOnboardingDataSources] = useState<DataSourceInfo[]>([])
  const listRef = useRef<HTMLDivElement>(null)
  const { sendMessage, messages, isStreaming, approveCheckpoint, checkpoint, tableConfirm, approveTableConfirm, rejectTableConfirm } = useChat()
  const isHistory = useChatStore((s) => s.isHistory)
  const { templates, addTemplate, removeTemplate, hasTemplate } = useAnalysisTemplates()

  // 合并 Props 数据源和引导加载的数据源
  const effectiveDataSources = useMemo(() => {
    const existingIds = new Set(dataSources.map((d) => d.id))
    const merged = [...dataSources]
    for (const ds of onboardingDataSources) {
      if (!existingIds.has(ds.id)) {
        merged.push(ds)
      }
    }
    return merged
  }, [dataSources, onboardingDataSources])

  // 主数据源（第一个选中的）
  const primaryDs = effectiveDataSources.find((ds) => ds.id === selectedDsIds[0])
  // 关联数据源（其余选中的）
  const joinDsList = useMemo(() =>
    selectedDsIds.slice(1).map((id) => effectiveDataSources.find((ds) => ds.id === id)).filter(Boolean) as DataSourceInfo[],
    [selectedDsIds, effectiveDataSources])

  // 引导组件加载示例数据后的回调
  const handleOnboardingReady = useCallback((dsInfo: DataSourceInfo, sampleQuestion: string) => {
    setOnboardingDataSources((prev) => {
      if (prev.some((d) => d.id === dsInfo.id)) return prev
      return [...prev, dsInfo]
    })
    setSelectedDsIds([dsInfo.id])
    sendMessage(sampleQuestion, dsInfo.id)
  }, [sendMessage])

  // 从其他页面跳转过来时，自动发起分析（默认自动匹配角色）
  useEffect(() => {
    if (prefilledDsId && prefilledQuestion && messages.length === 0) {
      sendMessage(prefilledQuestion, prefilledDsId, undefined, 'auto')
    }
  }, [])

  // 自动滚动到底部
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [messages])

  // 拉取一键分析预设模板
  useEffect(() => {
    client.get<PresetTemplate[]>('/templates')
      .then(({ data }) => setPresets(Array.isArray(data) ? data : []))
      .catch(() => { /* 模板拉取失败不阻塞主流程 */ })
  }, [])

  const handleSend = () => {
    if (!inputValue.trim() || selectedDsIds.length === 0) return
    sendMessage(inputValue.trim(), selectedDsIds[0], selectedDsIds.slice(1), role)
    setInputValue('')
  }

  // 点击一键分析模板：自动选中数据源 + 设置角色 + 发起分析
  const handleTemplateClick = (tpl: PresetTemplate) => {
    if (isStreaming) return
    const ds = selectedDsIds[0]
      ? effectiveDataSources.find((d) => d.id === selectedDsIds[0])
      : effectiveDataSources[0]
    if (!ds) {
      message.warning('请先上传或加载示例数据')
      return
    }
    const roleKey = tpl.role_key || 'auto'
    setSelectedDsIds([ds.id])
    setRole(roleKey)
    setInputValue(tpl.question)
    sendMessage(tpl.question, ds.id, undefined, roleKey)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleApprove = (checkId: string) => {
    approveCheckpoint(checkId, 'approved')
  }

  const handleReject = (checkId: string) => {
    approveCheckpoint(checkId, 'rejected')
  }

  /* 判断最后一轮分析是否完成（有图表/表格） */
  const lastDoneMsg = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i]
      if (m.role === 'assistant' && (m.charts?.length || m.tables?.length)) {
        return m
      }
    }
    return null
  }, [messages])

  const handleDownloadResult = () => {
    if (!lastDoneMsg) return
    const result = {
      question: (() => {
        for (let i = messages.length - 1; i >= 0; i--) {
          if (messages[i].role === 'user') return messages[i].content
        }
        return '未知'
      })(),
      answer: lastDoneMsg.content,
      charts: lastDoneMsg.charts || [],
      tables: lastDoneMsg.tables || [],
      exportedAt: new Date().toISOString(),
    }
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `analysis_${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  /* 生成 PDF 分析报告 */
  const [isGeneratingReport, setIsGeneratingReport] = useState(false)
  const handleGenerateReport = async () => {
    if (messages.length === 0) return
    setIsGeneratingReport(true)
    try {
      await exportPdfReport(messages, {
        title: '掌柜数据分析报告',
        dataSource: primaryDs?.name || '未知数据源',
      })
      message.success('报告已生成并下载')
    } catch (e: any) {
      message.error(e?.message || '报告生成失败')
    } finally {
      setIsGeneratingReport(false)
    }
  }

  /* 图表下钻：点击图表元素后发起明细查询 */
  const handleChartDrilldown = (params: { category: string; value: number; chartType: string; title?: string }) => {
    if (selectedDsIds.length === 0 || isStreaming) return
    const question = `请展示「${params.category}」的详细明细数据，包含所有字段`
    sendMessage(question, selectedDsIds[0], selectedDsIds.slice(1), role)
  }

  // 建议问题
  const suggested = useMemo(() => {
    if (!primaryDs?.columns_meta || primaryDs.columns_meta.length === 0) return []
    return suggestQuestions(primaryDs.name, primaryDs.columns_meta)
  }, [primaryDs])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 96px)' }}>
      {/* 无数据源状态 - 显示引导 */}
      {effectiveDataSources.length === 0 && messages.length === 0 && (
        <OnboardingGuide onDataSourceReady={handleOnboardingReady} />
      )}

      {/* 审批弹窗 */}
      {checkpoint && (
        <ApprovalModal
          open={!!checkpoint}
          checkId={checkpoint.checkId}
          action={checkpoint.action}
          detail={checkpoint.detail}
          onApprove={handleApprove}
          onReject={handleReject}
        />
      )}

      {/* 多表确认弹窗 */}
      {tableConfirm && (
        <TableConfirmModal
          open={!!tableConfirm}
          checkId={tableConfirm.checkId}
          message={tableConfirm.message}
          candidates={tableConfirm.candidates}
          currentDsId={selectedDsIds[0]}
          onConfirm={approveTableConfirm}
          onReject={rejectTableConfirm}
        />
      )}

      {/* 消息列表 */}
      <div ref={listRef} style={{ flex: 1, overflowY: 'auto', padding: '0 0 16px' }}>
        {/* 历史对话提示横幅 */}
        {isHistory && messages.length > 0 && (
          <div style={{
            background: 'linear-gradient(135deg, #16233a, #1a2330)',
            border: '1px solid #243040',
            borderRadius: 6,
            padding: '8px 16px',
            margin: '0 0 16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: 13,
            color: '#60a5fa',
          }}>
            <span>
              <InfoCircleOutlined style={{ marginRight: 6 }} />
              正在查看历史对话（只读）
            </span>
            <Button
              size="small"
              type="link"
              onClick={() => window.location.href = '/chat'}
              style={{ color: '#60a5fa', fontSize: 12 }}
            >
              新建对话
            </Button>
          </div>
        )}
        {messages.length === 0 ? (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              color: '#5b6674',
            }}
          >
            <ThunderboltOutlined style={{ fontSize: 48, color: '#60a5fa', marginBottom: 20 }} />
            <div style={{ fontSize: 16, fontWeight: 600, color: '#d5dbe3', marginBottom: 8 }}>
              开始智能分析
            </div>
            <div style={{ fontSize: 13, color: '#5b6674', marginBottom: 28 }}>
              选择数据源，输入你的分析问题
            </div>
            <div style={{ width: 520, maxWidth: '90vw' }}>
              <div style={{
                display: 'flex', gap: 8, alignItems: 'flex-end',
                padding: '6px',
                background: '#111826',
                border: '1px solid #243040',
                borderRadius: 8,
                boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
                transition: 'border-color 0.2s, box-shadow 0.2s',
                marginBottom: 12,
              }}
                onFocusCapture={(e) => {
                  const target = e.currentTarget as HTMLElement
                  target.style.borderColor = '#3b82f6'
                  target.style.boxShadow = '0 4px 16px rgba(59,130,246,0.15)'
                }}
                onBlurCapture={(e) => {
                  const target = e.currentTarget as HTMLElement
                  target.style.borderColor = '#243040'
                  target.style.boxShadow = '0 4px 16px rgba(0,0,0,0.3)'
                }}
              >
                <Select
                  mode="multiple"
                  placeholder="选择数据源（可多选）"
                  value={selectedDsIds}
                  onChange={(vals) => setSelectedDsIds(vals)}
                  style={{ minWidth: 200 }}
                  variant="borderless"
                  popupMatchSelectWidth={false}
                  maxTagCount={2}
                  options={effectiveDataSources.map((ds) => ({
                    label: `${ds.name} · ${ds.purpose || '通用'} (${ds.row_count.toLocaleString()}行)`,
                    value: ds.id,
                  }))}
                />
                <div style={{ width: 1, height: 22, background: '#243040', alignSelf: 'center' }} />
                <Select
                  value={role}
                  onChange={setRole}
                  options={ROLE_OPTIONS}
                  variant="borderless"
                  popupMatchSelectWidth={false}
                  style={{ minWidth: 120, maxWidth: 150, fontSize: 13 }}
                />
                <TextArea
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="输入分析问题..."
                  rows={1}
                  disabled={isStreaming}
                  autoSize={{ minRows: 1, maxRows: 4 }}
                  style={{
                    flex: 1, border: 'none', background: 'transparent',
                    fontSize: 14, resize: 'none', boxShadow: 'none',
                    padding: '6px 0',
                  }}
                  variant="borderless"
                />
                <Button
                  type="primary"
                  icon={<SendOutlined />}
                  onClick={handleSend}
                  loading={isStreaming}
                  disabled={!inputValue.trim() || selectedDsIds.length === 0}
                  style={{
                    borderRadius: 8, minWidth: 38, height: 38,
                    background: (!inputValue.trim() || selectedDsIds.length === 0) ? '#243040' : 'linear-gradient(135deg, #2563eb, #3b82f6)',
                    border: 'none',
                    boxShadow: (!inputValue.trim() || selectedDsIds.length === 0) ? 'none' : '0 2px 6px rgba(59,130,246,0.3)',
                  }}
                />
              </div>
              {/* 数据源详情引导 */}
              {primaryDs && (
                <div style={{
                  background: '#16233a',
                  borderRadius: 6,
                  padding: 12,
                  marginBottom: 12,
                  textAlign: 'left',
                }}>
                  <div style={{ fontSize: 12, color: '#8b96a3', marginBottom: 6 }}>
                    <InfoCircleOutlined /> 数据结构
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
                    {(primaryDs.columns_meta || []).slice(0, 6).map((col, i) => (
                      <Tag key={i} color="blue" style={{ fontSize: 11 }}>
                        {col.name}
                        <span style={{ color: '#8b96a3', marginLeft: 2 }}>({col.dtype})</span>
                      </Tag>
                    ))}
                    {(primaryDs.columns_meta || []).length > 6 && (
                      <Tag style={{ fontSize: 11 }}>+{(primaryDs.columns_meta || []).length - 6}列</Tag>
                    )}
                  </div>
                  {primaryDs.columns_meta && primaryDs.columns_meta.length > 0 && (
                    <div style={{ fontSize: 12, color: '#8b96a3' }}>
                      试试问：
                      {suggestQuestions(primaryDs.name, primaryDs.columns_meta).map((q, i) => (
                        <div
                          key={i}
                          style={{
                            cursor: 'pointer',
                            color: '#60a5fa',
                            marginTop: 4,
                            textDecoration: 'none',
                          }}
                          onClick={() => { setInputValue(q) }}
                          onMouseEnter={(e) => { e.currentTarget.style.textDecoration = 'underline' }}
                          onMouseLeave={(e) => { e.currentTarget.style.textDecoration = 'none' }}
                        >
                          「{q}」
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* 一键分析模板 */}
            {effectiveDataSources.length > 0 && presets.length > 0 && (
              <div style={{ width: 680, maxWidth: '90vw', marginTop: 8 }}>
                <div style={{ textAlign: 'center', fontSize: 13, color: '#5b6674', marginBottom: 14 }}>
                  <ThunderboltOutlined style={{ color: '#60a5fa', marginRight: 6 }} />
                  或选择一键分析模板
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, justifyContent: 'center' }}>
                  {presets.map((tpl) => {
                    const roleLabel = ROLE_OPTIONS.find((o) => o.value === tpl.role_key)?.label || '自动匹配'
                    return (
                      <div
                        key={tpl.id}
                        onClick={() => handleTemplateClick(tpl)}
                        style={{
                          width: 160,
                          padding: '14px 14px',
                          background: '#111826',
                          border: '1px solid #243040',
                          borderRadius: 8,
                          cursor: 'pointer',
                          textAlign: 'left',
                          transition: 'all 0.15s',
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.borderColor = '#3b82f6'
                          e.currentTarget.style.boxShadow = '0 4px 16px rgba(59,130,246,0.15)'
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.borderColor = '#243040'
                          e.currentTarget.style.boxShadow = 'none'
                        }}
                      >
                        <div style={{ fontSize: 13, fontWeight: 600, color: '#d5dbe3', marginBottom: 4 }}>
                          {tpl.name}
                        </div>
                        <div style={{ fontSize: 12, color: '#8b96a3', lineHeight: 1.5, minHeight: 34 }}>
                          {tpl.description}
                        </div>
                        <div style={{ marginTop: 8, fontSize: 11, color: '#60a5fa' }}>
                          {roleLabel}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        ) : (
          messages.map((msg) => (
            <MessageBubble
              key={msg.id}
              message={msg}
              onChartDrilldown={handleChartDrilldown}
            />
          ))
        )}
      </div>

      {/* 输入区域（仅在有消息时显示底部固定输入区，历史模式禁用） */}
      {messages.length > 0 && !isHistory && (
        <div style={{
          borderTop: '1px solid #243040',
          padding: '16px 0 4px',
          background: '#0b0f14',
        }}>
          <div style={{ maxWidth: 800, margin: '0 auto' }}>
            {/* 已选数据源标签 */}
            {selectedDsIds.length > 0 && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: 6,
                marginBottom: 8, fontSize: 12, color: '#8b96a3', flexWrap: 'wrap',
              }}>
                <span>数据源：</span>
                {selectedDsIds.map((id, idx) => {
                  const ds = effectiveDataSources.find((d) => d.id === id)
                  return (
                    <Tag
                      key={id}
                      color={idx === 0 ? 'blue' : 'purple'}
                      closable
                      closeIcon={<CloseOutlined style={{ fontSize: 10 }} />}
                      onClose={() => setSelectedDsIds((prev) => prev.filter((x) => x !== id))}
                      style={{
                        margin: 0, borderRadius: 4,
                        padding: '2px 8px', fontSize: 12,
                      }}
                    >
                      {idx === 0 ? '📊 ' : '🔗 '}{ds?.name || id.slice(0, 8)}
                    </Tag>
                  )
                })}
              </div>
            )}
            {/* 快捷问题推荐 + 模板（非历史模式） */}
            {primaryDs && !isStreaming && !isHistory && (
              <div style={{ marginBottom: 8 }}>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {suggested.map((q, i) => (
                    <Button
                      key={i}
                      size="small"
                      type="default"
                      onClick={() => setInputValue(q)}
                      style={{
                        borderRadius: 6,
                        fontSize: 11,
                        borderColor: '#243040',
                        color: '#8b96a3',
                        background: '#111826',
                        padding: '0 10px',
                        height: 26,
                        transition: 'all 0.15s',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = '#3b82f6'
                        e.currentTarget.style.color = '#60a5fa'
                        e.currentTarget.style.background = '#16233a'
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = '#243040'
                        e.currentTarget.style.color = '#8b96a3'
                        e.currentTarget.style.background = '#111826'
                      }}
                    >
                      {q}
                    </Button>
                  ))}
                  {/* 一键模板下拉 */}
                  {presets.length > 0 && (
                    <Dropdown
                      trigger={['click']}
                      menu={{
                        items: presets.map((tpl) => ({
                          key: tpl.id,
                          label: (
                            <span>
                              <span style={{ fontWeight: 600 }}>{tpl.name}</span>
                              <span style={{ marginLeft: 8, fontSize: 11, color: '#60a5fa' }}>
                                {ROLE_OPTIONS.find((o) => o.value === tpl.role_key)?.label || '自动匹配'}
                              </span>
                            </span>
                          ),
                        })),
                        onClick: ({ key }) => {
                          const tpl = presets.find((t) => t.id === key)
                          if (tpl) handleTemplateClick(tpl)
                        },
                      }}
                    >
                      <Button
                        size="small"
                        type="default"
                        icon={<ThunderboltOutlined />}
                        style={{
                          borderRadius: 6,
                          fontSize: 11,
                          borderColor: '#d4af37',
                          color: '#d4af37',
                          background: '#16233a',
                          padding: '0 10px',
                          height: 26,
                        }}
                      >
                        一键模板
                      </Button>
                    </Dropdown>
                  )}
                  {/* 我的模板 */}
                  {templates.map((t) => (
                    <Tooltip key={t.id} title="点击删除">
                      <Button
                        size="small"
                        type="default"
                        onClick={() => {
                          if (inputValue === t.question) {
                            removeTemplate(t.id)
                          } else {
                            setInputValue(t.question)
                          }
                        }}
                        style={{
                          borderRadius: 6,
                          fontSize: 11,
                          borderColor: '#d4af37',
                          color: '#d4af37',
                          background: '#16233a',
                          padding: '0 10px',
                          height: 26,
                        }}
                      >
                        <StarFilled style={{ fontSize: 10, marginRight: 2, color: '#d4af37' }} />
                        {t.label}
                      </Button>
                    </Tooltip>
                  ))}
                </div>
              </div>
            )}
            {/* 数据源选择（多选） */}
            {selectedDsIds.length === 0 && messages.length > 0 && (
              <div style={{ marginBottom: 8 }}>
                <Select
                  mode="multiple"
                  placeholder="选择数据源（可多选关联表）"
                  value={selectedDsIds}
                  onChange={(vals) => setSelectedDsIds(vals)}
                  style={{ minWidth: 260 }}
                  size="small"
                  popupMatchSelectWidth={false}
                  maxTagCount={2}
                  options={effectiveDataSources.map((ds) => ({
                    label: `${ds.name} · ${ds.purpose || '通用'} (${ds.row_count.toLocaleString()}行)`,
                    value: ds.id,
                  }))}
                />
              </div>
            )}
            <div style={{
              display: 'flex', gap: 8, alignItems: 'flex-end',
              padding: '6px',
              background: '#111826',
              border: '1px solid #243040',
              borderRadius: 8,
              boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
              transition: 'border-color 0.2s, box-shadow 0.2s',
            }}
              onFocusCapture={(e) => {
                const target = e.currentTarget as HTMLElement
                target.style.borderColor = '#3b82f6'
                target.style.boxShadow = '0 4px 16px rgba(59,130,246,0.15)'
              }}
              onBlurCapture={(e) => {
                const target = e.currentTarget as HTMLElement
                target.style.borderColor = '#243040'
                target.style.boxShadow = '0 4px 16px rgba(0,0,0,0.3)'
              }}
            >
              <Select
                value={role}
                onChange={setRole}
                options={ROLE_OPTIONS}
                variant="borderless"
                size="small"
                popupMatchSelectWidth={false}
                style={{ minWidth: 120, maxWidth: 150, fontSize: 13 }}
              />
              <TextArea
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="输入你的分析问题..."
                rows={1}
                disabled={isStreaming}
                autoSize={{ minRows: 1, maxRows: 4 }}
                style={{
                  flex: 1, border: 'none', background: 'transparent',
                  fontSize: 14, resize: 'none', boxShadow: 'none',
                  padding: '4px 0',
                }}
                variant="borderless"
              />
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handleSend}
                loading={isStreaming}
                disabled={!inputValue.trim() || selectedDsIds.length === 0}
                style={{
                  borderRadius: 8, minWidth: 38, height: 38,
                  background: (!inputValue.trim() || selectedDsIds.length === 0) ? '#243040' : 'linear-gradient(135deg, #2563eb, #3b82f6)',
                  border: 'none',
                  boxShadow: (!inputValue.trim() || selectedDsIds.length === 0) ? 'none' : '0 2px 6px rgba(59,130,246,0.3)',
                }}
              />
              {lastDoneMsg && (
                <Tooltip title="下载分析结果 (JSON)">
                  <Button
                    icon={<DownloadOutlined />}
                    onClick={handleDownloadResult}
                    size="small"
                    type="text"
                    style={{ color: '#5b6674', borderRadius: 8 }}
                  />
                </Tooltip>
              )}
              {messages.length >= 2 && !isStreaming && (
                <Tooltip title="生成 PDF 分析报告">
                  <Button
                    icon={<FilePdfOutlined />}
                    onClick={handleGenerateReport}
                    loading={isGeneratingReport}
                    size="small"
                    type="text"
                    style={{ color: '#ef4444', borderRadius: 8 }}
                  />
                </Tooltip>
              )}
              {/* 保存为分析模板（仅非历史模式） */}
              {!isHistory && inputValue.trim() && !hasTemplate(inputValue.trim()) && (
                <Tooltip title="保存为分析模板，方便复用">
                  <Button
                    icon={<StarOutlined />}
                    onClick={() => addTemplate(inputValue.trim())}
                    size="small"
                    type="text"
                    style={{ color: '#d4af37', borderRadius: 8 }}
                  />
                </Tooltip>
              )}
              {!isHistory && inputValue.trim() && hasTemplate(inputValue.trim()) && (
                <Tooltip title="已保存为模板，点击取消">
                  <Button
                    icon={<StarFilled />}
                    onClick={() => {
                      const t = templates.find((t) => t.question === inputValue.trim())
                      if (t) removeTemplate(t.id)
                    }}
                    size="small"
                    type="text"
                    style={{ color: '#d4af37', borderRadius: 8 }}
                  />
                </Tooltip>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/* 多表选择确认弹窗 */
function TableConfirmModal({
  open, checkId, message, candidates, currentDsId, onConfirm, onReject,
}: {
  open: boolean
  checkId: string
  message: string
  candidates: TableCandidate[]
  currentDsId: string
  onConfirm: (checkId: string, selectedIds: string[]) => void
  onReject: (checkId: string) => void
}) {
  // 过滤掉当前已选的数据源，避免重复
  const otherCandidates = candidates.filter((c) => c.id !== currentDsId)
  const [selected, setSelected] = useState<string[]>([])

  return (
    <Modal
      title={
        <Space>
          <ExclamationCircleOutlined style={{ color: '#d4af37' }} />
          <span>关联数据表确认</span>
        </Space>
      }
      open={open}
      onCancel={() => onReject(checkId)}
      footer={
        <Space>
          <Button onClick={() => onReject(checkId)}>不需要</Button>
          <Button type="primary" onClick={() => onConfirm(checkId, selected)} disabled={selected.length === 0}>
            确认使用选中表
          </Button>
        </Space>
      }
      closable={false}
      maskClosable={false}
      width={520}
    >
      <Paragraph>
        <Text>{message}</Text>
      </Paragraph>
      {otherCandidates.length === 0 ? (
        <Paragraph type="secondary" style={{ fontSize: 13 }}>
          资源库中没有找到其他可关联的数据表。当前使用的数据源已包含所有可用字段。是否继续分析？
        </Paragraph>
      ) : (
        <>
          <Paragraph type="secondary" style={{ fontSize: 12 }}>
            AI 建议关联以下数据表来更好地回答你的问题，请勾选需要的表：
          </Paragraph>
          <div style={{ maxHeight: 260, overflowY: 'auto' }}>
            <Checkbox.Group value={selected} onChange={(vals) => setSelected(vals as string[])} style={{ width: '100%' }}>
              {otherCandidates.map((c) => (
                <div
                  key={c.id}
                  style={{
                    border: '1px solid #243040',
                    borderRadius: 6,
                    padding: 10,
                    marginBottom: 8,
                    cursor: 'pointer',
                  }}
                >
                  <Checkbox value={c.id}>
                    <span style={{ fontWeight: 500 }}>{c.name}</span>
                    <Tag color={(c.purpose || '').includes('订单') ? 'green' : (c.purpose || '').includes('客户') ? 'orange' : 'blue'} style={{ marginLeft: 6, fontSize: 11 }}>
                      {c.purpose || '通用数据'}
                    </Tag>
                    <span style={{ color: '#5b6674', fontSize: 11, marginLeft: 4 }}>{c.row_count} 行</span>
                  </Checkbox>
                  <div style={{ marginTop: 4, marginLeft: 24, fontSize: 11, color: '#8b96a3' }}>
                    {(c.columns || []).slice(0, 5).map((col, i) => (
                      <Tag key={i} style={{ fontSize: 10 }}>{col.name}</Tag>
                    ))}
                    {(c.columns || []).length > 5 && <span>+{(c.columns || []).length - 5}列</span>}
                  </div>
                </div>
              ))}
            </Checkbox.Group>
          </div>
        </>
      )}
    </Modal>
  )
}

export default ChatContainer
