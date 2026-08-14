import { useEffect, useState } from 'react'
import { Layout, Typography, Tag, Tooltip } from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'
import { WarningOutlined } from '@ant-design/icons'
import Logo from './Logo'
import client from '../../api/client'
import type { ConfigResponse } from '../../api/types'

const { Header: AntHeader } = Layout
const { Title } = Typography

const PAGE_TITLES: Record<string, string> = {
  '/chat': '智能分析',
  '/dashboard': '数据看板',
  '/forecast': '预测分析',
  '/data': '数据管理',
  '/settings': '系统设置',
}

function Header() {
  const location = useLocation()
  const navigate = useNavigate()
  const [aiConfigured, setAiConfigured] = useState(true)
  const currentPath = '/' + location.pathname.split('/')[1]
  const pageTitle = PAGE_TITLES[currentPath] || ''

  // 全局检测 AI 服务是否已配置，未配置时在顶部提供一致引导
  useEffect(() => {
    client
      .get<ConfigResponse>('/config')
      .then(({ data }) => setAiConfigured(data.configured !== false))
      .catch(() => setAiConfigured(true))
  }, [location.pathname])

  return (
    <AntHeader
      style={{
        background: '#0b0f14',
        padding: '0 28px',
        borderBottom: '1px solid #263242',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: 56,
        lineHeight: '56px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <Logo size={32} />
        <span style={{ fontSize: 15, fontWeight: 600, color: '#dde3ea', letterSpacing: -0.3 }}>
          {pageTitle || '掌柜 BizMaster'}
        </span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        {!aiConfigured && (
          <Tooltip title="尚未配置 AI 服务的 API Key，智能分析与预测解读暂不可用。点击前往配置">
            <Tag
              style={{
                margin: 0,
                borderRadius: 4,
                background: '#2a1a1a',
                color: '#f87171',
                border: '1px solid #4a2626',
                fontSize: 11,
                cursor: 'pointer',
              }}
              onClick={() => navigate('/settings')}
            >
              <WarningOutlined style={{ marginRight: 4 }} />
              AI 未接入
            </Tag>
          </Tooltip>
        )}
        <Tag style={{ margin: 0, borderRadius: 4, background: '#1a2330', color: '#d4af37', border: '1px solid #3a3a2a', fontSize: 11 }}>
          v0.1.1
        </Tag>
      </div>
    </AntHeader>
  )
}

export default Header
