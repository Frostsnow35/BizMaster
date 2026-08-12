import { Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from 'antd'
import Sidebar from './components/Layout/Sidebar'
import Header from './components/Layout/Header'
import ErrorBoundary from './components/ErrorBoundary'
import ChatPage from './pages/ChatPage'
import DataManagePage from './pages/DataManagePage'
import SettingsPage from './pages/SettingsPage'

const { Content } = Layout

function App() {
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sidebar />
      <Layout>
        <Header />
        <Content style={{ padding: '20px 28px', overflow: 'auto', background: '#f9fafb' }}>
          <ErrorBoundary>
            <Routes>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/chat/:sessionId" element={<ChatPage />} />
            <Route path="/data" element={<DataManagePage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
          </ErrorBoundary>
        </Content>
      </Layout>
    </Layout>
  )
}

export default App
