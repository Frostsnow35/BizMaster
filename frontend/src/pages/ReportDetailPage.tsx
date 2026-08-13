import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Card, Tag, Space, Typography, Button, Spin, Empty, Divider, message } from 'antd'
import { ArrowLeftOutlined, FilePdfOutlined } from '@ant-design/icons'
import ReactMarkdown from 'react-markdown'
import client from '../api/client'
import type { AnalysisReport, ReportChart, ReportTable } from '../api/types'
import ChartCard from '../components/Chat/ChartCard'
import TableCard from '../components/Chat/TableCard'
import { exportReportPdf } from '../utils/generateReport'

const { Title, Text } = Typography

const ROLE_LABELS: Record<string, string> = {
  data_analyst: '数据分析师',
  operations_analyst: '电商运营专家',
  finance_analyst: '财务经营分析师',
}

const roleLabel = (key: string) => ROLE_LABELS[key] || '自动匹配'

/* Markdown 深色主题渲染样式 */
const reportComponents = {
  h2: ({ children }: any) => (
    <h2 style={{ fontSize: 17, fontWeight: 600, color: '#d4af37', margin: '20px 0 8px', borderBottom: '1px solid #263242', paddingBottom: 6 }}>
      {children}
    </h2>
  ),
  h3: ({ children }: any) => (
    <h3 style={{ fontSize: 15, fontWeight: 600, color: '#dde3ea', margin: '14px 0 6px' }}>{children}</h3>
  ),
  ul: ({ children }: any) => <ul style={{ paddingLeft: 20, margin: '6px 0' }}>{children}</ul>,
  ol: ({ children }: any) => <ol style={{ paddingLeft: 20, margin: '6px 0' }}>{children}</ol>,
  li: ({ children }: any) => <li style={{ marginBottom: 4, color: '#d5dbe3', lineHeight: 1.8 }}>{children}</li>,
  p: ({ children }: any) => <p style={{ color: '#d5dbe3', lineHeight: 1.8, margin: '6px 0' }}>{children}</p>,
  strong: ({ children }: any) => <strong style={{ color: '#e6c56b' }}>{children}</strong>,
  table: ({ children }: any) => (
    <div style={{ overflowX: 'auto', margin: '12px 0' }}>
      <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: 13 }}>{children}</table>
    </div>
  ),
  th: ({ children }: any) => (
    <th style={{ borderBottom: '2px solid #263242', padding: '8px 12px', textAlign: 'left', fontWeight: 600, color: '#9aa7b5', background: '#16233a' }}>
      {children}
    </th>
  ),
  td: ({ children }: any) => (
    <td style={{ borderBottom: '1px solid #263242', padding: '8px 12px', color: '#d5dbe3' }}>{children}</td>
  ),
}

/* 判断是否为标准表格结构（columns + 数组 data） */
function isTabularTable(t: any): t is ReportTable {
  return !!t && Array.isArray(t.columns) && Array.isArray(t.data)
}

/** 渲染单个表格：标准表格用 TableCard，键值对数据用简单列表兜底 */
function renderTable(t: any, idx: number) {
  if (isTabularTable(t)) {
    return <TableCard key={idx} columns={t.columns} data={t.data} />
  }
  if (t && typeof t.data === 'object' && t.data !== null && !Array.isArray(t.data)) {
    const entries = Object.entries(t.data as Record<string, any>)
    if (entries.length === 0) return null
    return (
      <div
        key={idx}
        style={{ background: '#121a26', borderRadius: 6, padding: '12px 16px', marginBottom: 12, boxShadow: '0 1px 2px rgba(0,0,0,0.35)' }}
      >
        <Space wrap size={[24, 8]}>
          {entries.map(([k, v]) => (
            <span key={k} style={{ fontSize: 13 }}>
              <Text type="secondary" style={{ marginRight: 6 }}>{k}</Text>
              <Text style={{ color: '#e6c56b', fontWeight: 600 }}>{String(v)}</Text>
            </span>
          ))}
        </Space>
      </div>
    )
  }
  return null
}

function ReportDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [report, setReport] = useState<AnalysisReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)

  const fetchReport = useCallback(async () => {
    if (!id) return
    setLoading(true)
    setError(null)
    try {
      const { data } = await client.get<AnalysisReport>(`/reports/${id}`)
      setReport(data)
    } catch (e: any) {
      setError(e?.response?.data?.detail || '报告加载失败')
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    fetchReport()
  }, [fetchReport])

  const handleExportPdf = async () => {
    if (!report) return
    setExporting(true)
    try {
      await exportReportPdf(report)
      message.success('报告已导出')
    } catch (e: any) {
      message.error(e?.message || '导出失败')
    } finally {
      setExporting(false)
    }
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 120 }}>
        <Spin size="large" />
      </div>
    )
  }

  if (error || !report) {
    return (
      <div style={{ maxWidth: 720 }}>
        <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/reports')} style={{ color: '#9aa7b5', marginBottom: 12 }}>
          返回报告列表
        </Button>
        <Empty description={error || '报告不存在'} />
      </div>
    )
  }

  const charts: ReportChart[] = Array.isArray(report.charts) ? report.charts : []
  const tables: ReportTable[] = Array.isArray(report.tables) ? report.tables : []
  const sections: string[] = Array.isArray(report.sections) ? report.sections : []

  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/reports')} style={{ color: '#9aa7b5' }}>
          返回报告列表
        </Button>
        <Button icon={<FilePdfOutlined />} loading={exporting} onClick={handleExportPdf} style={{ borderColor: '#3a3a2a', color: '#d4af37' }}>
          导出 PDF
        </Button>
      </div>

      <Card
        style={{ background: '#121a26', border: '1px solid #263242', borderRadius: 8, boxShadow: '0 1px 3px rgba(0,0,0,0.4)' }}
        styles={{ body: { padding: '28px 32px' } }}
      >
        {/* 标题与元信息 */}
        <Title level={4} style={{ color: '#dde3ea', marginBottom: 12 }}>
          {report.title || '分析报告'}
        </Title>

        <Space wrap size={8} style={{ marginBottom: 8 }}>
          <Tag color="gold" style={{ color: '#d4af37', background: '#1a2330', borderColor: '#3a3a2a' }}>
            {roleLabel(report.role_key)}
          </Tag>
          <Tag color={report.status === 'success' ? 'green' : 'red'}>
            {report.status === 'success' ? '成功' : '失败'}
          </Tag>
          {report.created_at && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              {new Date(report.created_at).toLocaleString('zh-CN')}
            </Text>
          )}
        </Space>

        {sections.length > 0 && (
          <Space wrap size={4} style={{ marginBottom: 4 }}>
            {sections.map((s) => (
              <Tag key={s} style={{ color: '#9aa7b5', background: '#0f1723', borderColor: '#263242', fontSize: 12 }}>
                {s}
              </Tag>
            ))}
          </Space>
        )}

        {report.error && (
          <div style={{ color: '#ef4444', marginBottom: 12, fontSize: 13 }}>{report.error}</div>
        )}

        <Divider style={{ borderColor: '#263242', margin: '16px 0' }} />

        {/* 文字结论 */}
        {report.summary ? (
          <ReactMarkdown components={reportComponents}>{report.summary}</ReactMarkdown>
        ) : (
          <Text type="secondary">（无文字结论）</Text>
        )}

        {/* 图表 */}
        {charts.length > 0 && (
          <>
            <Divider orientation="left" style={{ color: '#9aa7b5', borderColor: '#263242', margin: '24px 0 16px' }}>
              数据图表
            </Divider>
            {charts.map((chart, idx) =>
              chart.echarts_option ? (
                <ChartCard key={idx} option={chart.echarts_option} title={chart.title} />
              ) : null,
            )}
          </>
        )}

        {/* 表格 */}
        {tables.length > 0 && (
          <>
            <Divider orientation="left" style={{ color: '#9aa7b5', borderColor: '#263242', margin: '24px 0 16px' }}>
              数据明细
            </Divider>
            {tables.map((t, idx) => renderTable(t, idx))}
          </>
        )}
      </Card>
    </div>
  )
}

export default ReportDetailPage
