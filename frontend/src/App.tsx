import { Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from 'antd'
import Sidebar from './components/Layout/Sidebar'
import Header from './components/Layout/Header'
import ErrorBoundary from './components/ErrorBoundary'
import ChatPage from './pages/ChatPage'
import DataManagePage from './pages/DataManagePage'
import SettingsPage from './pages/SettingsPage'
import SchedulePage from './pages/SchedulePage'
import ReportDetailPage from './pages/ReportDetailPage'
import DashboardPage from './pages/DashboardPage'
import ForecastPage from './pages/ForecastPage'

const { Content } = Layout

function App() {
  return (
    <>
      <Layout style={{ minHeight: '100vh', background: '#0b0f14' }}>
        <Sidebar />
        <Layout>
          <Header />
          <Content style={{ padding: '20px 28px', overflow: 'auto', background: '#0b0f14' }}>
            <ErrorBoundary>
              <Routes>
                <Route path="/" element={<Navigate to="/chat" replace />} />
                <Route path="/chat" element={<ChatPage />} />
                <Route path="/chat/:sessionId" element={<ChatPage />} />
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/forecast" element={<ForecastPage />} />
                <Route path="/data" element={<DataManagePage />} />
                <Route path="/reports" element={<SchedulePage />} />
                <Route path="/reports/:id" element={<ReportDetailPage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Routes>
            </ErrorBoundary>
          </Content>
        </Layout>
      </Layout>
    </>
  )
}

export default App
