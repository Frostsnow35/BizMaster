import { useEffect } from 'react'
import { Spin } from 'antd'
import { useLocation, useParams } from 'react-router-dom'
import ChatContainer from '../components/Chat/ChatContainer'
import { useDataSources } from '../hooks/useDataSources'
import { useChatStore } from '../store/chatStore'

interface NavState {
  dataSourceId?: string
  question?: string
}

function ChatPage() {
  const { dataSources, loading } = useDataSources()
  const location = useLocation()
  const { sessionId } = useParams<{ sessionId?: string }>()
  const navState = location.state as NavState | undefined
  const prefilledDsId = navState?.dataSourceId
  const prefilledQuestion = navState?.question
  const loadSession = useChatStore((s) => s.loadSession)
  const currentSessionId = useChatStore((s) => s.currentSessionId)
  const clearMessages = useChatStore((s) => s.clearMessages)

  // 加载历史会话
  useEffect(() => {
    if (sessionId && sessionId !== currentSessionId) {
      loadSession(sessionId)
    } else if (!sessionId && !prefilledDsId && currentSessionId !== null) {
      // 进入新对话，清空消息
      clearMessages()
    }
  }, [sessionId])

  return (
    <div style={{ height: '100%' }}>
      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 80 }}>
          <Spin tip="加载数据源...">
            <div style={{ minHeight: 60 }} />
          </Spin>
        </div>
      ) : (
        <ChatContainer
          dataSources={dataSources}
          prefilledDsId={prefilledDsId}
          prefilledQuestion={prefilledQuestion}
        />
      )}
    </div>
  )
}

export default ChatPage
