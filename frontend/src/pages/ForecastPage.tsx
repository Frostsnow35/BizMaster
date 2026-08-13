import { useState, useMemo } from 'react'
import { Select, Button, Spin, Empty, Tag, Alert } from 'antd'
import { LineChartOutlined, ThunderboltOutlined } from '@ant-design/icons'
import ChartCard from '../components/Chat/ChartCard'
import { useDataSources } from '../hooks/useDataSources'
import client from '../api/client'
import type { ForecastResponse } from '../api/types'

/* 预测指标选项 */
const METRIC_OPTIONS = [
  { value: 'sales', label: '销售额' },
  { value: 'orders', label: '订单量' },
  { value: 'qty', label: '销量' },
]

/* 预测方法选项 */
const METHOD_OPTIONS = [
  { value: 'linear', label: '线性回归' },
  { value: 'moving_avg', label: '移动平均' },
]

/* 预测周期选项 */
const PERIOD_OPTIONS = [
  { value: 7, label: '未来 7 天' },
  { value: 14, label: '未来 14 天' },
  { value: 30, label: '未来 30 天' },
  { value: 90, label: '未来 90 天' },
]

function ForecastPage() {
  const { dataSources, loading } = useDataSources()
  const [dataSourceId, setDataSourceId] = useState<string | undefined>()
  const [metric, setMetric] = useState('sales')
  const [method, setMethod] = useState('linear')
  const [periods, setPeriods] = useState(30)
  const [result, setResult] = useState<ForecastResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [generating, setGenerating] = useState(false)

  const handleGenerate = async () => {
    if (!dataSourceId) return
    setGenerating(true)
    setResult(null)
    setError(null)
    try {
      const { data } = await client.post<ForecastResponse>('/forecast', {
        data_source_id: dataSourceId,
        metric,
        method,
        periods,
      })
      setResult(data)
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      setError(detail ? String(detail) : '预测失败，请检查参数后重试')
    } finally {
      setGenerating(false)
    }
  }

  /* 由预测响应构建实际值 + 预测值双线趋势图 */
  const chartOption = useMemo(() => {
    if (!result) return null
    return {
      tooltip: { trigger: 'axis' },
      legend: { data: ['实际值', '预测值'], bottom: 0 },
      grid: { left: 60, right: 30, top: 40, bottom: 50 },
      xAxis: {
        type: 'category',
        data: result.dates,
        axisLabel: { color: '#8b96a3' },
      },
      yAxis: {
        type: 'value',
        name: result.metric_label,
        nameTextStyle: { color: '#8b96a3' },
      },
      series: [
        {
          name: '实际值',
          type: 'line',
          data: result.actual,
          smooth: true,
          showSymbol: false,
          itemStyle: { color: '#6366f1' },
        },
        {
          name: '预测值',
          type: 'line',
          data: result.forecast,
          smooth: true,
          showSymbol: false,
          lineStyle: { type: 'dashed' },
          itemStyle: { color: '#d4af37' },
        },
      ],
    }
  }, [result])

  return (
    <div>
      {/* 参数选择区 */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, alignItems: 'center', flexWrap: 'wrap' }}>
        <Select
          placeholder="选择数据源"
          value={dataSourceId}
          onChange={setDataSourceId}
          style={{ minWidth: 260 }}
          loading={loading}
          options={dataSources.map((ds) => ({
            value: ds.id,
            label: `${ds.name}（${ds.purpose || '通用'}）`,
          }))}
        />
        <Select value={metric} onChange={setMetric} style={{ minWidth: 120 }} options={METRIC_OPTIONS} />
        <Select value={method} onChange={setMethod} style={{ minWidth: 130 }} options={METHOD_OPTIONS} />
        <Select value={periods} onChange={setPeriods} style={{ minWidth: 130 }} options={PERIOD_OPTIONS} />
        <Button
          type="primary"
          icon={<ThunderboltOutlined />}
          onClick={handleGenerate}
          loading={generating}
          disabled={!dataSourceId}
        >
          生成预测
        </Button>
      </div>

      {generating && <Spin style={{ display: 'block', margin: '60px auto' }} />}

      {error && <Alert type="error" style={{ marginBottom: 20 }} message={error} showIcon />}

      {result && (
        <>
          {/* AI 预测解读区 */}
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
                <LineChartOutlined style={{ color: '#d4af37' }} />
                <span style={{ fontWeight: 600, color: '#dde3ea' }}>预测解读</span>
                <Tag style={{ margin: 0, fontSize: 11 }} color="geekblue">{result.metric_label}</Tag>
                <Tag style={{ margin: 0, fontSize: 11 }}>{result.method_label}</Tag>
              </div>
              <div
                style={{
                  color: result.insight.source === 'unavailable' ? '#8b96a3' : '#aeb8c4',
                  lineHeight: 1.8,
                }}
              >
                {result.insight.text}
              </div>
            </div>
          )}

          {chartOption && (
            <ChartCard
              option={chartOption}
              title={`${result.metric_label}趋势预测（未来 ${result.periods} ${result.freq_label}）`}
            />
          )}
        </>
      )}

      {!result && !generating && !error && (
        <Empty
          style={{ marginTop: 60 }}
          description="选择数据源与预测参数后点击「生成预测」，系统将基于历史趋势外推未来走向"
        />
      )}
    </div>
  )
}

export default ForecastPage
