import { Modal } from 'antd'
import { useState, useRef } from 'react'
import ReactECharts from 'echarts-for-react'

interface Props {
  option: any
  title?: string
  dataSourceId?: string
  onDrilldown?: (params: { category: string; value: number; chartType: string }) => void
}

/**
 * @brief 确保 ECharts option 含有中文字体配置
 */
function ensureFont(option: any): any {
  if (!option || typeof option !== 'object') {
    return { textStyle: { fontFamily: 'PingFang SC, Microsoft YaHei, sans-serif' } }
  }
  if (!option.textStyle) {
    option = { textStyle: {}, ...option }
  }
  if (!option.textStyle.fontFamily) {
    option.textStyle.fontFamily = 'PingFang SC, Microsoft YaHei, sans-serif'
  }
  return option
}

function ChartCard({ option, title, dataSourceId, onDrilldown }: Props) {
  const [fullscreen, setFullscreen] = useState(false)
  const chartRef = useRef<any>(null)
  const mergedOption = ensureFont(option)

  /* ECharts 点击事件 → 下钻 */
  const onChartReady = (echarts: any) => {
    chartRef.current = echarts
    if (onDrilldown) {
      echarts.on('click', (params: any) => {
        // 饼图点击扇区，直角坐标系点击柱子/点
        if (params.name && params.value !== undefined) {
          const value = typeof params.value === 'number' ? params.value : parseFloat(params.value) || 0
          onDrilldown({
            category: params.name,
            value,
            chartType: params.seriesType || mergedOption?.series?.[0]?.type || 'bar',
          })
        }
      })
    }
  }

  return (
    <div
      style={{
        cursor: onDrilldown ? 'pointer' : 'default',
        background: '#ffffff',
        borderRadius: 10,
        padding: 12,
        marginBottom: 12,
        boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
      }}
    >
      <div onClick={() => setFullscreen(true)}>
        <ReactECharts
          option={mergedOption}
          style={{ height: 320 }}
          notMerge
          onChartReady={onChartReady}
        />
        {title && <div style={{ textAlign: 'center', color: '#9ca3af', fontSize: 12, marginTop: 4 }}>{title}</div>}
      </div>
      {onDrilldown && (
        <div style={{ textAlign: 'center', marginTop: 4 }}>
          <span style={{ fontSize: 11, color: '#b0b0b0' }}>点击图表元素查看明细数据</span>
        </div>
      )}
      <Modal open={fullscreen} onCancel={() => setFullscreen(false)} footer={null} width={900} title={title}>
        <ReactECharts option={mergedOption} style={{ height: 520 }} notMerge />
      </Modal>
    </div>
  )
}

export default ChartCard
