import { useState } from 'react'
import { Select, Button, Empty, Spin, Tag, Alert } from 'antd'
import { BarChartOutlined, ThunderboltOutlined } from '@ant-design/icons'
import ChartCard from '../components/Chat/ChartCard'
import { useDataSources } from '../hooks/useDataSources'
import client from '../api/client'
import type { DashboardResponse, DashboardKpi } from '../api/types'

/* KPI 数值格式化：按 kind 区分货币、百分比与普通数值 */
function formatKpi(kpi: DashboardKpi): string {
  const v = kpi.value ?? 0
  if (kpi.kind === 'currency') {
    return `¥${v.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}`
  }
  if (kpi.kind === 'percent') {
    return `${v.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}%`
  }
  return `${v.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}${kpi.unit ? ' ' + kpi.unit : ''}`
}

function DashboardPage() {
  const { dataSources, loading } = useDataSources()
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [result, setResult] = useState<DashboardResponse | null>(null)
  const [generating, setGenerating] = useState(false)

  const handleGenerate = async () => {
    if (selectedIds.length === 0) return
    setGenerating(true)
    setResult(null)
    try {
      const { data } = await client.post<DashboardResponse>('/dashboard', {
        data_source_ids: selectedIds,
      })
      setResult(data)
    } catch (err) {
      console.error('生成看板失败:', err)
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div>
      {/* 数据源多选与生成控制区 */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, alignItems: 'center' }}>
        <Select
          mode="multiple"
          placeholder="选择数据源（可多选）"
          value={selectedIds}
          onChange={setSelectedIds}
          style={{ minWidth: 420, flex: 1 }}
          loading={loading}
          options={dataSources.map((ds) => ({
            value: ds.id,
            label: `${ds.name}（${ds.purpose || '通用'}）`,
          }))}
        />
        <Button
          type="primary"
          icon={<ThunderboltOutlined />}
          onClick={handleGenerate}
          loading={generating}
          disabled={selectedIds.length === 0}
        >
          生成看板
        </Button>
      </div>

      {generating && <Spin style={{ display: 'block', margin: '60px auto' }} />}

      {result && (
        <>
          {/* AI 经营解读区 */}
          {result.insight && (
            <div
              style={{
                background: '#121a26',
                borderRadius: 6,
                padding: '16px 20px',
                marginBottom: 20,
                border: '1px solid #263242',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <BarChartOutlined style={{ color: '#d4af37' }} />
                <span style={{ fontWeight: 600, color: '#dde3ea' }}>经营解读</span>
                {result.insight.source === 'rule' && (
                  <Tag style={{ margin: 0, fontSize: 11 }}>规则生成</Tag>
                )}
              </div>
              <div style={{ color: '#aeb8c4', lineHeight: 1.8 }}>{result.insight.text}</div>
            </div>
          )}

          {/* 部分数据源失败提示 */}
          {result.errors && result.errors.length > 0 && (
            <Alert
              type="warning"
              style={{ marginBottom: 20 }}
              message="部分数据源生成失败"
              description={result.errors.map((e) => e.error).join('；')}
              showIcon
            />
          )}

          {result.sections.length === 0 && <Empty description="暂无数据源，请先上传数据" />}

          {/* 分区并列展示 */}
          {result.sections.map((section) => (
            <div key={section.data_source_id} style={{ marginBottom: 28 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                <span style={{ fontSize: 16, fontWeight: 700, color: '#dde3ea' }}>{section.name}</span>
                {section.purpose && <Tag style={{ margin: 0 }}>{section.purpose}</Tag>}
                <span style={{ fontSize: 12, color: '#6b7686' }}>
                  {section.row_count.toLocaleString()} 行
                </span>
              </div>

              {/* KPI 卡片 */}
              {section.kpis.length > 0 && (
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
                    gap: 12,
                    marginBottom: 12,
                  }}
                >
                  {section.kpis.map((kpi) => (
                    <div
                      key={kpi.key}
                      style={{
                        background: '#121a26',
                        borderRadius: 6,
                        padding: '14px 16px',
                        border: '1px solid #263242',
                      }}
                    >
                      <div style={{ fontSize: 12, color: '#6b7686', marginBottom: 6 }}>{kpi.label}</div>
                      <div style={{ fontSize: 22, fontWeight: 700, color: '#d4af37' }}>{formatKpi(kpi)}</div>
                    </div>
                  ))}
                </div>
              )}

              {/* 图表 */}
              {section.charts.length > 0 && (
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(420px, 1fr))',
                    gap: 12,
                  }}
                >
                  {section.charts.map((chart, idx) => (
                    <ChartCard key={idx} option={chart.echarts_option} title={chart.title} />
                  ))}
                </div>
              )}
            </div>
          ))}
        </>
      )}

      {!result && !generating && (
        <Empty
          style={{ marginTop: 60 }}
          description="选择数据源后点击「生成看板」，系统将智能识别字段并生成经营全景"
        />
      )}
    </div>
  )
}

export default DashboardPage
