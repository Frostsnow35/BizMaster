import { useState } from 'react'
import { Button, Card, Typography, message, Tag } from 'antd'
import { ThunderboltOutlined, UploadOutlined, FireOutlined, RiseOutlined, PieChartOutlined, SwapOutlined } from '@ant-design/icons'
import client from '../../api/client'
import type { DataSourceInfo } from '../../api/types'

const { Text, Title } = Typography

interface Props {
  onDataSourceReady: (ds: DataSourceInfo, sampleQuestion: string) => void
}

/* 示例问题列表 */
const SAMPLE_QUESTIONS: { icon: React.ReactNode; title: string; question: string }[] = [
  {
    icon: <RiseOutlined style={{ color: '#34d399' }} />,
    title: '销售趋势',
    question: '最近30天每日销售额趋势如何？按渠道拆分',
  },
  {
    icon: <PieChartOutlined style={{ color: '#d4af37' }} />,
    title: '品类分析',
    question: '各品类销售额占比是多少？哪个品类卖得最好？',
  },
  {
    icon: <SwapOutlined style={{ color: '#3b82f6' }} />,
    title: '对比分析',
    question: '对比淘宝和抖音渠道的客单价和退货率',
  },
]

function OnboardingGuide({ onDataSourceReady }: Props) {
  const [loadingSample, setLoadingSample] = useState(false)
  const [loadedDsId, setLoadedDsId] = useState<string | null>(null)

  const handleLoadSample = async () => {
    setLoadingSample(true)
    try {
      const { data } = await client.post('/sample-data?sample_key=orders')
      message.success(`已加载示例数据：${data.name}（${data.row_count.toLocaleString()} 行）`)

      // 构造 DataSourceInfo 格式
      const dsInfo: DataSourceInfo = {
        id: data.data_source_id,
        name: data.name,
        file_type: data.file_type,
        table_name: data.table_name,
        row_count: data.row_count,
        columns_meta: data.columns_meta || [],
        purpose: (data as any).description || '订单数据',
        platform: data.platform?.platform || 'generic',
        platform_name: data.platform?.platform_name,
        created_at: new Date().toISOString(),
      }
      setLoadedDsId(data.data_source_id)
      // 自动发起第一个分析问题
      onDataSourceReady(dsInfo, SAMPLE_QUESTIONS[0].question)
    } catch (err: any) {
      const detail = err?.response?.data?.detail || '加载失败，请检查后端服务是否启动'
      message.error(detail)
    } finally {
      setLoadingSample(false)
    }
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '60vh',
        padding: '40px 20px',
      }}
    >
      {/* 主标题 */}
      <div style={{ textAlign: 'center', marginBottom: 32 }}>
        <div
          style={{
            width: 72,
            height: 72,
            borderRadius: 20,
            background: 'linear-gradient(135deg, #2563eb, #3b82f6)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 20px',
            boxShadow: '0 8px 24px rgba(59,130,246,0.25)',
          }}
        >
          <ThunderboltOutlined style={{ fontSize: 36, color: '#fff' }} />
        </div>
        <Title level={3} style={{ margin: 0, fontWeight: 600, color: '#d5dbe3' }}>
          欢迎使用掌柜，电商经营数据分析
        </Title>
        <Text type="secondary" style={{ fontSize: 14, marginTop: 8, display: 'block' }}>
          用自然语言对话，轻松掌握经营数据
        </Text>
      </div>

      {/* 快速开始卡片 */}
      <div style={{ maxWidth: 560, width: '100%' }}>
        {/* 方案A: 加载示例数据 */}
        <Card
          style={{
            marginBottom: 16,
            borderRadius: 8,
            border: '1px solid #243040',
            boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
          }}
          styles={{ body: { padding: '20px 24px' } }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 10,
                background: '#16233a',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <FireOutlined style={{ color: '#3b82f6', fontSize: 20 }} />
            </div>
            <div style={{ flex: 1 }}>
              <Text strong style={{ fontSize: 15 }}>快速体验</Text>
              <Text type="secondary" style={{ display: 'block', fontSize: 13, marginTop: 4 }}>
                加载内置的示例订单数据，立即体验 AI 分析能力
              </Text>
              <div style={{ marginTop: 12 }}>
                <Button
                  type="primary"
                  icon={loadingSample ? undefined : <ThunderboltOutlined />}
                  loading={loadingSample}
                  onClick={handleLoadSample}
                  disabled={!!loadedDsId}
                  style={{
                    borderRadius: 8,
                    background: loadedDsId ? '#243040' : 'linear-gradient(135deg, #2563eb, #3b82f6)',
                    border: 'none',
                  }}
                >
                  {loadedDsId ? '已加载 · 分析中...' : '加载示例数据 · 立即体验'}
                </Button>
              </div>
            </div>
          </div>
        </Card>

        {/* 方案B: 上传自己的数据 */}
        <Card
          style={{
            borderRadius: 8,
            border: '1px solid #243040',
            boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
          }}
          styles={{ body: { padding: '20px 24px' } }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 10,
                background: '#2a2414',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <UploadOutlined style={{ color: '#d4af37', fontSize: 20 }} />
            </div>
            <div style={{ flex: 1 }}>
              <Text strong style={{ fontSize: 15 }}>导入我的数据</Text>
              <Text type="secondary" style={{ display: 'block', fontSize: 13, marginTop: 4 }}>
                上传 CSV 或 Excel 文件（支持淘宝/拼多多/抖音/京东导出的订单数据）
              </Text>
              <div style={{ marginTop: 12 }}>
                <Button
                  icon={<UploadOutlined />}
                  onClick={() => (window.location.href = '/data')}
                  style={{ borderRadius: 8 }}
                >
                  前往上传数据
                </Button>
              </div>
            </div>
          </div>
        </Card>

        {/* 可以分析什么 */}
        <div style={{ marginTop: 28, textAlign: 'center' }}>
          <Text type="secondary" style={{ fontSize: 12, marginBottom: 10, display: 'block' }}>
            试试这些问题
          </Text>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center' }}>
            {SAMPLE_QUESTIONS.map((q, i) => (
              <Tag
                key={i}
                style={{
                  cursor: 'pointer',
                  padding: '4px 12px',
                  borderRadius: 6,
                  fontSize: 12,
                  border: '1px solid #243040',
                  background: '#111826',
                  color: '#8b96a3',
                }}
              >
                {q.icon} {q.title}
              </Tag>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

export default OnboardingGuide
