import { useCallback, useEffect, useRef, useState } from 'react'
import { useChatStore, createMessage, type ThinkingStep, type OutputFormat, type TableCandidate } from '../store/chatStore'

interface CheckpointState {
  checkId: string
  action: string
  detail: string
}

interface TableConfirmState {
  checkId: string
  message: string
  candidates: TableCandidate[]
}

// 开发模式走 Vite 代理；Electron 生产模式以 file:// 加载，host 为空，需使用绝对地址
const WS_URL = import.meta.env.DEV
  ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/chat`
  : 'ws://127.0.0.1:8000/ws/chat'
const MAX_RECONNECT = 5
const RECONNECT_DELAY = 3000

/**
 * @brief 将 LLM 原始回答清洗为纯净要点文本
 * 删除表格行、标题行、连续空行，确保回答区只显示人类可读的要点
 */
function cleanBulletContent(raw: string): string {
  return raw
    .split('\n')
    .filter(line => {
      const trimmed = line.trim()
      if (!trimmed) return false  // 先去除空行
      if (/^\s*\|.*\|\s*$/.test(line)) return false  // 表格行
      if (/^#{1,3}\s/.test(trimmed)) return false  // Markdown 标题
      return true
    })
    .join('\n')
    .replace(/\n{2,}/g, '\n\n')  // 压缩连续空行
    .trim()
}

export function useChat() {
  const messages = useChatStore((s) => s.messages)
  const isStreaming = useChatStore((s) => s.isStreaming)
  const addMessage = useChatStore((s) => s.addMessage)
  const updateMessage = useChatStore((s) => s.updateMessage)
  const setStreaming = useChatStore((s) => s.setStreaming)

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectCountRef = useRef(0)
  const assistantMsgIdRef = useRef<string | null>(null)
  const lastQuestionRef = useRef<string>('')
  const thinkingStepsRef = useRef<ThinkingStep[]>([])

  const [checkpoint, setCheckpoint] = useState<CheckpointState | null>(null)
  const [tableConfirm, setTableConfirm] = useState<TableConfirmState | null>(null)

  const appendThinkingStep = useCallback((step: ThinkingStep) => {
    thinkingStepsRef.current = [...thinkingStepsRef.current, step]
    const msgId = assistantMsgIdRef.current
    if (msgId) {
      updateMessage(msgId, { thinkingSteps: [...thinkingStepsRef.current] })
    }
  }, [updateMessage])

  // WebSocket 消息处理
  const handleWsMessage = useCallback(
    (raw: string) => {
      let event: any
      try {
        event = JSON.parse(raw)
      } catch {
        return
      }

      const msgId = assistantMsgIdRef.current
      const eventType: string = event.type || ''

      switch (eventType) {
        case 'planning': {
          const steps = event.steps || []
          if (steps.length > 0) {
            const stepDesc = steps.map((s: any, i: number) => `${i + 1}. ${s.description}`).join('\n')
            appendThinkingStep({ type: 'planning', content: stepDesc })
          }
          break
        }

        case 'step_result': {
          const desc = event.description || ''
          const results = event.results || []
          const successCount = results.filter((r: any) => r.success).length
          const totalCount = results.length
          appendThinkingStep({
            type: 'step_result',
            content: desc,
            successCount,
            totalCount,
          })
          break
        }

        case 'reflecting': {
          const notes = event.notes || []
          if (notes.length > 0) {
            appendThinkingStep({
              type: 'reflecting',
              content: notes.join('；'),
            })
          } else if (event.need_approval) {
            appendThinkingStep({ type: 'reflecting', content: '需要人工审批' })
          }
          break
        }

        case 'responding': {
          // 响应生成中：清洗后再展示，避免流式过程中出现原始表格标记
          if (msgId && event.response_preview) {
            updateMessage(msgId, {
              content: cleanBulletContent(event.response_preview),
              isStreaming: true,
            })
          }
          break
        }

        case 'done': {
          if (msgId) {
            const rawContent = event.final_response || ''
            const noTag = rawContent.replace(/\s*\[FORMAT:(?:table|report|bullet|chart)\]\s*$/m, '').trimEnd()
            const cleanContent = cleanBulletContent(noTag)
            // 用户明确要求图表时，初始格式直接展示图表
            const question = lastQuestionRef.current
            const wantsChart = /图|chart|plot|graph/i.test(question)
            const hasCharts = (event.charts?.length ?? 0) > 0
            updateMessage(msgId, {
              content: cleanContent,
              format: (wantsChart && hasCharts) ? 'chart' : 'bullet',
              formatVariants: event.format_variants || undefined,
              isStreaming: false,
              thinkingExpanded: false,
              charts: event.charts || undefined,
              tables: event.tables || undefined,
            })
            assistantMsgIdRef.current = null
            thinkingStepsRef.current = []
          }
          setStreaming(false)
          break
        }

        case 'human_checkpoint': {
          appendThinkingStep({
            type: 'reflecting',
            content: `需要人工审批: ${event.action || ''}`,
          })
          // 多表确认类型
          if (event.action === 'confirm_tables') {
            try {
              const detail = typeof event.detail === 'string' ? JSON.parse(event.detail) : event.detail
              setTableConfirm({
                checkId: event.check_id || '',
                message: detail.message || '请选择需要关联的数据表',
                candidates: detail.candidates || [],
              })
            } catch {
              setCheckpoint({
                checkId: event.check_id || '',
                action: event.action || '需要人工审批',
                detail: event.detail || '',
              })
            }
          } else {
            setCheckpoint({
              checkId: event.check_id || '',
              action: event.action || '需要人工审批',
              detail: event.detail || '',
            })
          }
          break
        }

        case 'approval_processed': {
          setCheckpoint(null)
          setTableConfirm(null)
          break
        }

        case 'error': {
          if (msgId) {
            const rawError = event.message || '分析过程出错'
            updateMessage(msgId, {
              content: rawError,
              msgType: 'error',
              isStreaming: false,
              thinkingExpanded: false,
            })
            assistantMsgIdRef.current = null
            thinkingStepsRef.current = []
          }
          setStreaming(false)
          break
        }

        default:
          break
      }
    },
    [appendThinkingStep, updateMessage, setStreaming],
  )

  // WebSocket 连接管理
  const connect = useCallback(() => {
    if (
      wsRef.current?.readyState === WebSocket.OPEN ||
      wsRef.current?.readyState === WebSocket.CONNECTING
    ) {
      return
    }

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      reconnectCountRef.current = 0
    }

    ws.onmessage = (e) => {
      handleWsMessage(e.data as string)
    }

    ws.onerror = () => {
      ws.close()
    }

    ws.onclose = () => {
      wsRef.current = null
      if (reconnectCountRef.current < MAX_RECONNECT) {
        reconnectCountRef.current++
        reconnectTimerRef.current = setTimeout(connect, RECONNECT_DELAY)
      }
    }
  }, [handleWsMessage])

  // 发送消息
  const sendMessage = useCallback(
    (content: string, dataSourceId: string, joinDataSourceIds?: string[], role?: string, reformat?: OutputFormat) => {
      const userMsg = createMessage({ role: 'user', content })
      addMessage(userMsg)

      // 助手占位消息：开始时有展开的思考区域
      const assistantMsg = createMessage({
        role: 'assistant',
        content: '',
        isStreaming: true,
        thinkingSteps: [],
        thinkingExpanded: true,
      })
      addMessage(assistantMsg)
      assistantMsgIdRef.current = assistantMsg.id
      lastQuestionRef.current = content
      thinkingStepsRef.current = []
      setStreaming(true)

      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        connect()
      }

      let sendAttempts = 0
      const MAX_SEND_ATTEMPTS = 50
      const trySend = () => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          const payload: Record<string, unknown> = {
            type: 'chat',
            content,
            data_source_id: dataSourceId,
          }
          if (reformat) {
            payload.reformat = reformat
          }
          if (joinDataSourceIds && joinDataSourceIds.length > 0) {
            payload.join_data_source_ids = joinDataSourceIds
          }
          if (role) {
            payload.role_key = role
          }
          wsRef.current.send(JSON.stringify(payload))
        } else if (sendAttempts < MAX_SEND_ATTEMPTS) {
          sendAttempts++
          setTimeout(trySend, 100)
        } else {
          const msgId = assistantMsgIdRef.current
          if (msgId) {
            updateMessage(msgId, {
              content: '无法连接到分析服务，请检查后端是否已启动',
              msgType: 'error',
              isStreaming: false,
              thinkingExpanded: false,
            })
            assistantMsgIdRef.current = null
            thinkingStepsRef.current = []
          }
          setStreaming(false)
        }
      }
      trySend()
    },
    [addMessage, setStreaming, connect, updateMessage],
  )

  // 审批操作
  const approveCheckpoint = useCallback(
    (checkId: string, result: 'approved' | 'rejected') => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({ type: 'human_approval', check_id: checkId, result }),
        )
      }
      setCheckpoint(null)
    },
    [],
  )

  // 多表确认操作
  const approveTableConfirm = useCallback(
    (checkId: string, selectedIds: string[]) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({
            type: 'human_approval',
            check_id: checkId,
            result: 'approved',
            selected_table_ids: selectedIds,
          }),
        )
      }
      setTableConfirm(null)
    },
    [],
  )

  const rejectTableConfirm = useCallback(
    (checkId: string) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({ type: 'human_approval', check_id: checkId, result: 'rejected' }),
        )
      }
      setTableConfirm(null)
    },
    [],
  )

  // 生命周期
  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
      }
      wsRef.current?.close()
    }
  }, [connect])

  return { messages, isStreaming, sendMessage, approveCheckpoint, checkpoint, tableConfirm, approveTableConfirm, rejectTableConfirm }
}
