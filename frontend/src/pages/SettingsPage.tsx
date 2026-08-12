import { useState } from 'react'
import { Typography, Form, Input, Select, Button, Card, message, Space, Divider } from 'antd'
import { SaveOutlined, ApiOutlined, InfoCircleOutlined } from '@ant-design/icons'
import { useAppStore } from '../store/appStore'
import client from '../api/client'

const { Title, Text } = Typography

function SettingsPage() {
  const { deepseekKey, setDeepseekKey } = useAppStore()
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    try {
      const values = form.getFieldsValue()
      setDeepseekKey(values.apiKey)

      // 持久化到 localStorage
      localStorage.setItem('deepseek_api_key', values.apiKey)
      localStorage.setItem('llm_provider', values.provider)
      localStorage.setItem('llm_model', values.model)

      // 同步到后端
      try {
        await client.post('/config', {
          provider: values.provider,
          model: values.model,
          api_key: values.apiKey,
        })
        message.success('配置已保存并同步到后端')
      } catch {
        message.success('配置已保存到本地，后端启动后自动同步')
      }
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleTestConnection = async () => {
    const key = form.getFieldValue('apiKey')
    if (!key) {
      message.warning('请先填写 API Key')
      return
    }
    try {
      const response = await fetch('https://api.deepseek.com/v1/models', {
        headers: { Authorization: `Bearer ${key}` },
      })
      if (response.ok) {
        message.success('连接测试成功')
      } else {
        message.error('连接测试失败，请检查 API Key')
      }
    } catch {
      message.error('网络连接失败，请检查网络')
    }
  }

  return (
    <div style={{ maxWidth: 640 }}>
      <Title level={4} style={{ marginBottom: 24 }}>系统设置</Title>

      <Card
        title="LLM 模型配置"
        style={{ marginBottom: 24 }}
        styles={{ body: { padding: 24 } }}
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            provider: localStorage.getItem('llm_provider') || 'deepseek',
            apiKey: localStorage.getItem('deepseek_api_key') || deepseekKey || '',
            model: localStorage.getItem('llm_model') || 'deepseek-chat',
          }}
        >
          <Form.Item label="模型提供商" name="provider">
            <Select
              options={[
                { label: 'DeepSeek（推荐）', value: 'deepseek' },
                { label: '通义千问（即将支持）', value: 'qwen', disabled: true },
              ]}
            />
          </Form.Item>

          <Form.Item
            label="API Key"
            name="apiKey"
            extra={
              <Text type="secondary">
                在{' '}
                <a href="https://platform.deepseek.com/api_keys" target="_blank" rel="noopener noreferrer">
                  DeepSeek 控制台
                </a>{' '}
                获取 API Key，支持支付宝充值
              </Text>
            }
          >
            <Input.Password placeholder="sk-..." />
          </Form.Item>

          <Form.Item label="模型" name="model">
            <Select
              options={[
                { label: 'deepseek-chat（快速对话）', value: 'deepseek-chat' },
                { label: 'deepseek-reasoner（深度思考）', value: 'deepseek-reasoner' },
              ]}
            />
          </Form.Item>

          <Space>
            <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={saving}>
              保存配置
            </Button>
            <Button icon={<ApiOutlined />} onClick={handleTestConnection}>
              测试连接
            </Button>
          </Space>
        </Form>
      </Card>

      <Card styles={{ body: { padding: 24 } }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <InfoCircleOutlined style={{ color: '#6366f1' }} />
          <Text strong>关于</Text>
        </div>
        <Divider style={{ margin: '8px 0 16px' }} />
        <div style={{ color: '#6b7280', lineHeight: 2 }}>
          掌柜 BizMaster v0.1.0 · 电商经营数据分析
          <br />
          面向中小电商商家的自助经营数据分析工具
          <br />
          <Text type="secondary" style={{ fontSize: 12 }}>
            FastAPI + LangGraph + React + DeepSeek
          </Text>
        </div>
      </Card>
    </div>
  )
}

export default SettingsPage
