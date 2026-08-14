import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Table, Button, Modal, Form, Input, Select, Switch, Tag, Space, Tabs, message, Popconfirm, Typography } from 'antd'
import { PlusOutlined, PlayCircleOutlined, EditOutlined, DeleteOutlined, FileTextOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import client from '../api/client'
import type { ReportSchedule, AnalysisReport, DataSourceInfo } from '../api/types'

const { Title, Text } = Typography

const FREQUENCY_LABELS: Record<string, string> = {
  hourly: '每小时',
  daily: '每天',
  weekly: '每周',
  monthly: '每月',
}

const ROLE_OPTIONS = [
  { value: 'auto', label: '自动匹配角色' },
  { value: 'data_analyst', label: '数据分析师' },
  { value: 'operations_analyst', label: '电商运营专家' },
  { value: 'finance_analyst', label: '财务经营分析师' },
]

const FREQUENCY_OPTIONS = [
  { value: 'hourly', label: '每小时' },
  { value: 'daily', label: '每天' },
  { value: 'weekly', label: '每周' },
  { value: 'monthly', label: '每月' },
]

function SchedulePage() {
  const navigate = useNavigate()
  const [schedules, setSchedules] = useState<ReportSchedule[]>([])
  const [reports, setReports] = useState<AnalysisReport[]>([])
  const [dataSources, setDataSources] = useState<DataSourceInfo[]>([])
  const [schedulesLoading, setSchedulesLoading] = useState(false)
  const [reportsLoading, setReportsLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<ReportSchedule | null>(null)
  const [runningId, setRunningId] = useState<string | null>(null)
  const [retryingId, setRetryingId] = useState<string | null>(null)
  const [form] = Form.useForm()

  const fetchSchedules = useCallback(async () => {
    setSchedulesLoading(true)
    try {
      const { data } = await client.get<ReportSchedule[]>('/schedules')
      setSchedules(data)
    } finally {
      setSchedulesLoading(false)
    }
  }, [])

  const fetchReports = useCallback(async () => {
    setReportsLoading(true)
    try {
      const { data } = await client.get<AnalysisReport[]>('/reports')
      setReports(data)
    } finally {
      setReportsLoading(false)
    }
  }, [])

  const fetchDataSources = useCallback(async () => {
    try {
      const { data } = await client.get<DataSourceInfo[]>('/data-sources')
      setDataSources(data)
    } catch {
      // 后端未就绪时静默处理
    }
  }, [])

  useEffect(() => {
    fetchSchedules()
    fetchReports()
    fetchDataSources()
  }, [fetchSchedules, fetchReports, fetchDataSources])

  const dsName = (id: string) => dataSources.find((d) => d.id === id)?.name || id.slice(0, 8)
  const roleLabel = (key: string) => ROLE_OPTIONS.find((o) => o.value === key)?.label || '自动匹配'

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ role_key: 'auto', frequency: 'daily', enabled: true })
    setModalOpen(true)
  }

  const openEdit = (s: ReportSchedule) => {
    setEditing(s)
    form.setFieldsValue({
      name: s.name,
      data_source_id: s.data_source_id,
      question: s.question,
      role_key: s.role_key,
      frequency: s.frequency,
      time: s.time,
      enabled: s.enabled,
    })
    setModalOpen(true)
  }

  const handleSubmit = async () => {
    const values = await form.validateFields()
    try {
      if (editing) {
        await client.put(`/schedules/${editing.id}`, values)
        message.success('任务已更新')
      } else {
        await client.post('/schedules', values)
        message.success('任务已创建')
      }
      setModalOpen(false)
      fetchSchedules()
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '操作失败')
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await client.delete(`/schedules/${id}`)
      message.success('已删除')
      fetchSchedules()
    } catch {
      message.error('删除失败')
    }
  }

  const handleToggleEnabled = async (s: ReportSchedule, enabled: boolean) => {
    try {
      await client.put(`/schedules/${s.id}`, { enabled })
      fetchSchedules()
    } catch {
      message.error('更新失败')
    }
  }

  const handleRunNow = async (s: ReportSchedule) => {
    setRunningId(s.id)
    try {
      await client.post(`/schedules/${s.id}/run`)
      message.success('报告已生成')
      fetchReports()
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '运行失败')
    } finally {
      setRunningId(null)
    }
  }

  const handleRetryReport = async (report: AnalysisReport) => {
    setRetryingId(report.id)
    try {
      await client.post(`/reports/${report.id}/retry`)
      message.success('已重新生成报告')
      fetchReports()
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '重试失败')
    } finally {
      setRetryingId(null)
    }
  }

  const scheduleColumns: ColumnsType<ReportSchedule> = [
    { title: '任务名称', dataIndex: 'name', key: 'name', width: 160, ellipsis: true },
    {
      title: '数据源',
      dataIndex: 'data_source_id',
      key: 'data_source_id',
      width: 140,
      render: (id: string) => <Tag>{dsName(id)}</Tag>,
    },
    {
      title: '分析问题',
      dataIndex: 'question',
      key: 'question',
      ellipsis: true,
      render: (q: string) => <Text style={{ color: '#d5dbe3' }}>{q}</Text>,
    },
    {
      title: '角色',
      dataIndex: 'role_key',
      key: 'role_key',
      width: 130,
      render: (k: string) => <Text type="secondary">{roleLabel(k)}</Text>,
    },
    {
      title: '频率',
      dataIndex: 'frequency',
      key: 'frequency',
      width: 90,
      render: (f: string) => <Tag color="blue">{FREQUENCY_LABELS[f] || f}</Tag>,
    },
    {
      title: '启用',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 70,
      render: (enabled: boolean, record) => (
        <Switch
          size="small"
          checked={enabled}
          onChange={(v) => handleToggleEnabled(record, v)}
        />
      ),
    },
    {
      title: '上次运行',
      dataIndex: 'last_run_at',
      key: 'last_run_at',
      width: 150,
      render: (t: string) => (
        <Text type="secondary" style={{ fontSize: 12 }}>
          {t ? new Date(t).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '未运行'}
        </Text>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 190,
      render: (_, record) => (
        <Space size={0}>
          <TooltipButton
            title="立即运行"
            icon={<PlayCircleOutlined />}
            loading={runningId === record.id}
            onClick={() => handleRunNow(record)}
          />
          <TooltipButton title="编辑" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          <Popconfirm title="确认删除" description="删除后不可恢复" onConfirm={() => handleDelete(record.id)} okText="删除" cancelText="取消">
            <Button type="text" danger size="small" icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const reportColumns: ColumnsType<AnalysisReport> = [
    { title: '报告标题', dataIndex: 'title', key: 'title', ellipsis: true, render: (t: string) => <Text style={{ color: '#d5dbe3' }}>{t}</Text> },
    {
      title: '角色',
      dataIndex: 'role_key',
      key: 'role_key',
      width: 130,
      render: (k: string) => <Text type="secondary">{roleLabel(k)}</Text>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (s: string) => <Tag color={s === 'success' ? 'green' : 'red'}>{s === 'success' ? '成功' : '失败'}</Tag>,
    },
    {
      title: '生成时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (t: string) => <Text type="secondary" style={{ fontSize: 12 }}>{new Date(t).toLocaleString('zh-CN')}</Text>,
    },
    {
      title: '操作',
      key: 'actions',
      width: 140,
      render: (_, record) => (
        <Space size={0}>
          <Button type="link" size="small" icon={<FileTextOutlined />} onClick={() => navigate(`/reports/${record.id}`)}>
            查看
          </Button>
          {record.status === 'failed' && (
            <Button
              type="link"
              size="small"
              icon={<PlayCircleOutlined />}
              loading={retryingId === record.id}
              onClick={() => handleRetryReport(record)}
            >
              重试
            </Button>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div style={{ maxWidth: 1080 }}>
      <Title level={4} style={{ marginBottom: 20 }}>定时报告</Title>

      <Tabs
        defaultActiveKey="schedules"
        items={[
          {
            key: 'schedules',
            label: '定时任务',
            children: (
              <Card
                title="自动分析任务"
                extra={<Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新建任务</Button>}
                styles={{ body: { padding: 0 } }}
              >
                <Table
                  columns={scheduleColumns}
                  dataSource={schedules}
                  rowKey="id"
                  loading={schedulesLoading}
                  pagination={{ pageSize: 10, showTotal: (t) => `共 ${t} 个任务` }}
                  locale={{ emptyText: '暂无定时任务，点击右上角「新建任务」创建' }}
                />
              </Card>
            ),
          },
          {
            key: 'reports',
            label: '报告记录',
            children: (
              <Card title="历史报告" styles={{ body: { padding: 0 } }}>
                <Table
                  columns={reportColumns}
                  dataSource={reports}
                  rowKey="id"
                  loading={reportsLoading}
                  pagination={{ pageSize: 10, showTotal: (t) => `共 ${t} 份报告` }}
                  locale={{ emptyText: '暂无报告记录' }}
                />
              </Card>
            ),
          },
        ]}
      />

      {/* 新建/编辑任务弹窗 */}
      <Modal
        title={editing ? '编辑定时任务' : '新建定时任务'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        okText="保存"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item label="任务名称" name="name" rules={[{ required: true, message: '请输入任务名称' }]}>
            <Input placeholder="例如：每日经营健康度报告" />
          </Form.Item>
          <Form.Item label="数据源" name="data_source_id" rules={[{ required: true, message: '请选择数据源' }]}>
            <Select
              placeholder="选择要分析的数据源"
              options={dataSources.map((d) => ({ value: d.id, label: d.name }))}
            />
          </Form.Item>
          <Form.Item label="分析问题" name="question" rules={[{ required: true, message: '请输入分析问题' }]}>
            <Input.TextArea rows={3} placeholder="例如：评估整体经营健康度，分析 GMV、订单量、客单价、退货率等核心指标" />
          </Form.Item>
          <Form.Item label="分析角色" name="role_key">
            <Select options={ROLE_OPTIONS} />
          </Form.Item>
          <Space size={16} align="start">
            <Form.Item label="执行频率" name="frequency" rules={[{ required: true }]}>
              <Select options={FREQUENCY_OPTIONS} style={{ width: 140 }} />
            </Form.Item>
            <Form.Item label="执行时间" name="time" extra="HH:MM（每日/每周/每月有效）">
              <Input placeholder="09:00" style={{ width: 120 }} />
            </Form.Item>
          </Space>
        </Form>
      </Modal>

    </div>
  )
}

/* 简化的带提示按钮 */
function TooltipButton({
  title,
  icon,
  loading,
  onClick,
}: {
  title: string
  icon: React.ReactNode
  loading?: boolean
  onClick: () => void
}) {
  return (
    <Button
      type="text"
      size="small"
      title={title}
      icon={icon}
      loading={loading}
      onClick={onClick}
    />
  )
}

export default SchedulePage
