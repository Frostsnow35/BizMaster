import React from 'react'
import ReactDOM from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import { ConfigProvider, theme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'
import './styles/global.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: '#3b82f6',
          colorInfo: '#60a5fa',
          colorLink: '#60a5fa',
          colorBgBase: '#0b0f14',
          colorBgContainer: '#121a26',
          colorBgElevated: '#1a2330',
          colorBorder: '#263242',
          colorBorderSecondary: '#243040',
          colorText: '#dde3ea',
          colorTextSecondary: '#8b96a3',
          colorTextTertiary: '#6b7686',
          colorTextQuaternary: '#5b6674',
          colorWarning: '#d4af37',
          borderRadius: 6,
        },
      }}
    >
      {/* HashRouter 兼容 Electron 生产模式 file:// 协议（BrowserRouter 无法匹配路径） */}
      <HashRouter>
        <App />
      </HashRouter>
    </ConfigProvider>
  </React.StrictMode>,
)
