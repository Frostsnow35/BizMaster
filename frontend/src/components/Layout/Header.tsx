import { Layout, Typography, Tag } from 'antd'
import { useLocation } from 'react-router-dom'
import Logo from './Logo'

const { Header: AntHeader } = Layout
const { Title } = Typography

const PAGE_TITLES: Record<string, string> = {
  '/chat': '智能分析',
  '/data': '数据管理',
  '/settings': '系统设置',
}

function Header() {
  const location = useLocation()
  const currentPath = '/' + location.pathname.split('/')[1]
  const pageTitle = PAGE_TITLES[currentPath] || ''

  return (
    <AntHeader
      style={{
        background: '#ffffff',
        padding: '0 28px',
        borderBottom: '1px solid #f3f4f6',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: 56,
        lineHeight: '56px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <Logo size={32} />
        <span style={{ fontSize: 15, fontWeight: 600, color: '#111827', letterSpacing: -0.3 }}>
          {pageTitle || '掌柜 BizMaster'}
        </span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Tag style={{ margin: 0, borderRadius: 6, background: '#eef2ff', color: '#6366f1', border: 'none', fontSize: 11 }}>
          v0.1.0
        </Tag>
      </div>
    </AntHeader>
  )
}

export default Header
