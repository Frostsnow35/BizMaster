import { useState, useEffect } from 'react'
import { Layout, Menu, Button, message } from 'antd'
import { MessageOutlined, DatabaseOutlined, SettingOutlined, PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'
import client from '../../api/client'
import Logo from './Logo'

const { Sider } = Layout

interface Session {
  session_id: string
  title: string
  message_count: number
  created_at: string
}

/* ── 侧边栏品牌色（深靛蓝）── */
const SIDEBAR_BG = '#111827'
const SIDEBAR_TEXT = '#e5e7eb'
const SIDEBAR_TEXT_DIM = '#9ca3af'
const SIDEBAR_HOVER = 'rgba(99,102,241,0.15)'
const SIDEBAR_ACTIVE = 'rgba(99,102,241,0.25)'

function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const [sessions, setSessions] = useState<Session[]>([])
  const [collapsed, setCollapsed] = useState(false)
  const currentSessionId = location.pathname.startsWith('/chat/')
    ? location.pathname.split('/chat/')[1]
    : null

  /* 修复 Ant Design Sider 内部容器变白 */
  useEffect(() => {
    const timer = setInterval(() => {
      const el = document.querySelector('.ant-layout-sider') as HTMLElement | null
      if (el) {
        el.style.setProperty('background', SIDEBAR_BG, 'important')
        const children = el.querySelector('.ant-layout-sider-children') as HTMLElement | null
        if (children && children.style.background !== SIDEBAR_BG) {
          children.style.setProperty('background', SIDEBAR_BG, 'important')
          children.style.setProperty('height', '100vh', 'important')
          children.style.setProperty('overflow', 'hidden', 'important')
        }
      }
    }, 500)
    return () => clearInterval(timer)
  }, [])

  const fetchSessions = async () => {
    try {
      const { data } = await client.get<Session[]>('/sessions')
      setSessions(data)
    } catch {
      // 后端未就绪时静默处理
    }
  }

  useEffect(() => {
    fetchSessions()
    const interval = setInterval(fetchSessions, 5000)
    return () => clearInterval(interval)
  }, [])

  const handleNewChat = () => {
    navigate('/chat')
  }

  const handleDeleteSession = async (id: string) => {
    try {
      await client.delete(`/sessions/${id}`)
      fetchSessions()
      // 仅当删除的是当前会话时才跳转
      if (id === currentSessionId) {
        navigate('/chat')
      }
    } catch {
      message.error('删除失败')
    }
  }

  const selectedKey = '/' + location.pathname.split('/')[1]

  return (
    <Sider
      width={220}
      collapsible
      collapsed={collapsed}
      onCollapse={setCollapsed}
      style={{ background: SIDEBAR_BG, display: 'flex', flexDirection: 'column', height: '100vh' }}
    >
      {/* Logo 区域 */}
      <div
        style={{
          height: 56,
          display: 'flex',
          alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'flex-start',
          gap: collapsed ? 0 : 10,
          paddingLeft: collapsed ? 0 : 20,
          color: '#fff',
          fontSize: collapsed ? 18 : 16,
          fontWeight: 700,
          cursor: 'pointer',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
        }}
        onClick={handleNewChat}
      >
        <Logo size={32} />
        {!collapsed && <span style={{ letterSpacing: 0.5 }}>电商分析</span>}
      </div>

      {/* 主导航 */}
      <Menu
        mode="inline"
        selectedKeys={[selectedKey]}
        style={{ background: 'transparent', borderRight: 'none', marginTop: 8 }}
        theme="dark"
        items={[
          { key: '/chat', icon: <MessageOutlined />, label: '智能分析' },
          { key: '/data', icon: <DatabaseOutlined />, label: '数据管理' },
          { key: '/settings', icon: <SettingOutlined />, label: '系统设置' },
        ]}
        onClick={({ key }) => {
          if (key.startsWith('/')) navigate(key)
        }}
      />

      {/* 历史会话分隔 */}
      {sessions.length > 0 && !collapsed && (
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '12px 16px 6px',
            color: SIDEBAR_TEXT_DIM,
            fontSize: 11,
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: 0.5,
          }}
        >
          <span>历史对话</span>
          <Button
            type="text"
            size="small"
            icon={<PlusOutlined />}
            style={{ color: SIDEBAR_TEXT_DIM }}
            onClick={handleNewChat}
          />
        </div>
      )}

      {/* 历史会话滚动列表 */}
      <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', paddingBottom: 8 }}>
        {!collapsed &&
          sessions.slice(0, 50).map((s) => (
            <div
              key={s.session_id}
              onClick={() => {
                if (currentSessionId === s.session_id) return  // 已在查看，不重复跳转
                navigate(`/chat/${s.session_id}`)
              }}
              style={{
                padding: '8px 16px',
                margin: '0 8px',
                borderRadius: 6,
                cursor: 'pointer',
                color: SIDEBAR_TEXT,
                fontSize: 13,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                transition: 'background 0.15s',
                background: currentSessionId === s.session_id ? SIDEBAR_ACTIVE : 'transparent',
                fontWeight: currentSessionId === s.session_id ? 600 : 400,
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = SIDEBAR_HOVER
              }}
              onMouseLeave={(e) => {
              const isActive = currentSessionId === s.session_id
              e.currentTarget.style.background = isActive ? SIDEBAR_ACTIVE : 'transparent'
            }}
            >
              <span
                style={{
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  flex: 1,
                }}
              >
                {s.title}
              </span>
              <Button
                type="text"
                size="small"
                icon={<DeleteOutlined />}
                style={{ color: 'rgba(255,255,255,0.35)' }}
                onClick={(e) => {
                  e.stopPropagation()
                  handleDeleteSession(s.session_id)
                }}
              />
            </div>
          ))}
      </div>
    </Sider>
  )
}

export default Sidebar
