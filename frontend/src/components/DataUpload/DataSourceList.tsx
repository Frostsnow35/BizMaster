import { Table, Button, Popconfirm, Space, Tag, message, Tooltip, Typography } from 'antd'
import { DeleteOutlined, DownloadOutlined, FileTextOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import type { ColumnsType } from 'antd/es/table'
import type { DataSourceInfo, ColumnMeta } from '../../api/types'

const { Text } = Typography

interface Props {
  dataSources: DataSourceInfo[]
  loading: boolean
  onDelete: (id: string) => Promise<void>
}

/* 根据数据源列名动态生成快捷分析问题（与 ChatContainer 共享逻辑） */
function generateQuickQuestions(ds: DataSourceInfo): string[] {
  const cols = ds.columns_meta || []
  const allText = (ds.name + ' ' + cols.map((c) => c.name).join(' ') + ' ' + (ds.purpose || '')).toLowerCase()
  const suggestions: string[] = []
  const isOrder = allText.includes('order') || allText.includes('订单') || allText.includes('销售') || allText.includes('实付') || allText.includes('支付')
  const isCustomer = allText.includes('customer') || allText.includes('客户') || allText.includes('会员') || allText.includes('用户')
  const isProduct = allText.includes('product') || allText.includes('商品') || allText.includes('类目') || allText.includes('品类') || allText.includes('sku')

  if (isOrder && (allText.includes('金额') || allText.includes('price') || allText.includes('amount') || allText.includes('total') || allText.includes('数量'))) {
    suggestions.push('近30天销售额趋势如何？')
    suggestions.push('各品类销售额占比排名')
    suggestions.push('本月累计GMV是多少？')
  }
  if (isOrder && (allText.includes('日期') || allText.includes('date') || allText.includes('time') || allText.includes('下单') || allText.includes('创建'))) {
    suggestions.push('最近30天每日订单量走势')
    suggestions.push('周末和工作日的销量对比')
  }
  if (isOrder && (allText.includes('退货') || allText.includes('退款') || allText.includes('退款'))) {
    suggestions.push('退货率最高的前5个商品')
  }
  if (isCustomer) {
    suggestions.push('客户复购率分析')
    suggestions.push('高价值客户有哪些特征？')
  }
  if (isProduct && !isOrder) {
    suggestions.push('各品类商品数量分布')
  }
  if (suggestions.length === 0) {
    suggestions.push('帮我预览一下数据概览')
    suggestions.push('数据中有哪些主要字段？')
    suggestions.push('各列数据分布情况如何？')
    suggestions.push('数据质量检查（缺失值/异常值）')
  }
  return suggestions.slice(0, 5)
}

/* 平台标签映射 */
const PLATFORM_LABELS: Record<string, { name: string; color: string }> = {
  taobao: { name: '淘宝', color: '#ff5000' },
  pinduoduo: { name: '拼多多', color: '#e02e24' },
  douyin: { name: '抖音', color: '#111' },
  jd: { name: '京东', color: '#c91623' },
  generic: { name: '通用', color: '#8c8c8c' },
}

function DataSourceList({ dataSources, loading, onDelete }: Props) {
  const navigate = useNavigate()

  const handleDelete = async (id: string, name: string) => {
    try {
      await onDelete(id)
      message.success(`已删除数据源「${name}」`)
    } catch {
      message.error('删除失败，请重试')
    }
  }

  const handleQuickAnalyze = (ds: DataSourceInfo, question: string) => {
    navigate('/chat', { state: { dataSourceId: ds.id, question } })
  }

  const fileTag = (ext?: string) => {
    if (!ext) return null
    const color = ext === 'csv' ? 'green' : 'blue'
    return <Tag color={color} style={{ margin: 0 }}>{ext.toUpperCase()}</Tag>
  }

  const formatSize = (kb?: number) => {
    if (!kb) return ''
    if (kb < 1024) return `${kb} KB`
    return `${(kb / 1024).toFixed(1)} MB`
  }

  const columns: ColumnsType<DataSourceInfo> = [
    {
      title: '数据源',
      dataIndex: 'name',
      key: 'name',
      width: 200,
      ellipsis: true,
      render: (name: string, record) => (
        <Space>
          <FileTextOutlined style={{ color: '#6366f1' }} />
          <span>{name}</span>
          {fileTag(record.file_type)}
          {record.platform && PLATFORM_LABELS[record.platform] && (
            <Tag
              color={PLATFORM_LABELS[record.platform].color}
              style={{ margin: 0, fontSize: 11, padding: '0 6px' }}
            >
              {PLATFORM_LABELS[record.platform].name}
            </Tag>
          )}
          {record.purpose && (
            <Tag color={record.purpose.includes('订单') ? 'green' : record.purpose.includes('客户') ? 'orange' : 'blue'} style={{ margin: 0 }}>
              {record.purpose}
            </Tag>
          )}
        </Space>
      ),
    },
    {
      title: '行数',
      dataIndex: 'row_count',
      key: 'row_count',
      width: 100,
      sorter: (a, b) => a.row_count - b.row_count,
      render: (count: number) => <Tag color="purple">{count.toLocaleString()} 行</Tag>,
    },
    {
      title: '大小',
      dataIndex: 'file_size_kb',
      key: 'file_size_kb',
      width: 80,
      render: (kb: number) => <span style={{ color: '#9ca3af', fontSize: 12 }}>{formatSize(kb)}</span>,
    },
    {
      title: '字段',
      dataIndex: 'columns_meta',
      key: 'columns_meta',
      ellipsis: true,
      render: (cols: DataSourceInfo['columns_meta']) => {
        if (!cols || cols.length === 0) return <span style={{ color: '#9ca3af' }}>暂无列信息</span>
        const names = cols.map((c) => c.name)
        return (
          <Tooltip title={names.join('、')}>
            <span style={{ fontSize: 12 }}>
              {names.slice(0, 5).join('、')}
              {names.length > 5 ? ` 等 ${names.length} 列` : ''}
            </span>
          </Tooltip>
        )
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      sorter: (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
      render: (time: string) => new Date(time).toLocaleString('zh-CN', {
        month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
      }),
    },
    {
      title: '操作',
      key: 'actions',
      width: 200,
      render: (_, record) => (
        <Space size={0}>
          <Tooltip title="快速分析">
            <Button
              type="link"
              icon={<ThunderboltOutlined />}
              size="small"
              onClick={() => {
                const questions = generateQuickQuestions(record)
                if (questions.length > 0) handleQuickAnalyze(record, questions[0])
              }}
            >
              快速分析
            </Button>
          </Tooltip>
          <Tooltip title="下载 CSV">
            <Button
              type="link"
              icon={<DownloadOutlined />}
              size="small"
              href={`/api/export/${record.id}`}
              target="_blank"
            />
          </Tooltip>
          <Popconfirm
            title="确认删除"
            description={`确定删除「${record.name}」？数据将无法恢复。`}
            onConfirm={() => handleDelete(record.id, record.name)}
            okText="确认删除"
            cancelText="取消"
          >
            <Button type="link" danger icon={<DeleteOutlined />} size="small">
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <Table
      columns={columns}
      dataSource={dataSources}
      rowKey="id"
      loading={loading}
      pagination={{ pageSize: 10, showTotal: (total) => `共 ${total} 个数据源` }}
      locale={{ emptyText: '暂无数据源，请点击右上角「上传数据」添加' }}
      expandable={{
        expandedRowRender: (record) => {
          const questions = generateQuickQuestions(record)
          const cols = record.columns_meta || []

          return (
            <div style={{ padding: '8px 0' }}>
              {/* 平台识别信息 */}
              {record.platform && record.platform !== 'generic' && PLATFORM_LABELS[record.platform] && (
                <div style={{ marginBottom: 12 }}>
                  <Tag color={PLATFORM_LABELS[record.platform].color} style={{ fontSize: 12 }}>
                    {PLATFORM_LABELS[record.platform].name} 平台数据
                  </Tag>
                  {record.column_mapping && Object.keys(record.column_mapping).length > 0 && (
                    <Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>
                      已自动识别 {Object.keys(record.column_mapping).length} 个关键字段
                    </Text>
                  )}
                </div>
              )}

              {/* 列信息预览 */}
              {cols.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>字段列表：</Text>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                    {cols.map((col, i) => (
                      <Tag key={i} color="blue" style={{ fontSize: 11 }}>
                        {col.name}
                        <Text type="secondary" style={{ fontSize: 10, marginLeft: 2 }}>({col.dtype})</Text>
                      </Tag>
                    ))}
                  </div>
                </div>
              )}

              {/* 快捷分析问题 */}
              <div>
                <Text strong style={{ fontSize: 13 }}>
                  <ThunderboltOutlined style={{ color: '#6366f1', marginRight: 4 }} />
                  快捷分析：
                </Text>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
                  {questions.map((q, i) => (
                    <Button
                      key={i}
                      size="small"
                      type="default"
                      onClick={() => handleQuickAnalyze(record, q)}
                      style={{
                        borderRadius: 16,
                        fontSize: 12,
                        borderColor: '#e5e7eb',
                        color: '#4b5563',
                        transition: 'all 0.15s',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = '#6366f1'
                        e.currentTarget.style.color = '#6366f1'
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = '#e5e7eb'
                        e.currentTarget.style.color = '#4b5563'
                      }}
                    >
                      {q}
                    </Button>
                  ))}
                </div>
              </div>
            </div>
          )
        },
        rowExpandable: () => true,
      }}
    />
  )
}

export default DataSourceList
