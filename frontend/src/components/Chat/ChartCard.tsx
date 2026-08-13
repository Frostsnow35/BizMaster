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
  const monoFont = 'JetBrains Mono, Consolas, "PingFang SC", "Microsoft YaHei", monospace'
  const lightColor = '#dde3ea'
  if (!option || typeof option !== 'object') {
    return { textStyle: { fontFamily: monoFont, color: lightColor } }
  }
  if (!option.textStyle) {
    option.textStyle = {}
  }
  if (!option.textStyle.fontFamily) {
    option.textStyle.fontFamily = monoFont
  }
  if (!option.textStyle.color) {
    option.textStyle.color = lightColor
  }
  // 深色背景下标题、图例与坐标轴标签浅色适配
  if (option.title && !option.title.textStyle) {
    option.title.textStyle = { color: lightColor }
  }
  if (option.legend && !option.legend.textStyle) {
    option.legend.textStyle = { color: lightColor }
  }
  const adaptAxis = (axis: any) => {
    if (!axis) return
    if (!axis.axisLabel) axis.axisLabel = {}
    if (!axis.axisLabel.color) axis.axisLabel.color = '#8b96a3'
    if (axis.nameTextStyle && !axis.nameTextStyle.color) {
      axis.nameTextStyle.color = '#8b96a3'
    }
  }
  adaptAxis(option.xAxis)
  adaptAxis(option.yAxis)
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
        background: '#121a26',
        borderRadius: 6,
        padding: 12,
        marginBottom: 12,
        boxShadow: '0 1px 2px rgba(0, 0, 0, 0.35)',
      }}
    >
      <div onClick={() => setFullscreen(true)}>
        <ReactECharts
          option={mergedOption}
          style={{ height: 320 }}
          notMerge
          onChartReady={onChartReady}
        />
        {title && <div style={{ textAlign: 'center', color: '#6b7686', fontSize: 12, marginTop: 4 }}>{title}</div>}
      </div>
      {onDrilldown && (
        <div style={{ textAlign: 'center', marginTop: 4 }}>
          <span style={{ fontSize: 11, color: '#6b7686' }}>点击图表元素查看明细数据</span>
        </div>
      )}
      <Modal open={fullscreen} onCancel={() => setFullscreen(false)} footer={null} width={900} title={title}>
        <ReactECharts option={mergedOption} style={{ height: 520 }} notMerge />
      </Modal>
    </div>
  )
}

export default ChartCard
