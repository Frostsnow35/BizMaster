import { create } from 'zustand'
import client from '../api/client'

export interface ThinkingStep {
  type: 'planning' | 'step_result' | 'reflecting' | 'responding'
  content: string
  stepIndex?: number
  successCount?: number
  totalCount?: number
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  msgType?: 'error' | 'human_checkpoint'
  isStreaming?: boolean
  thinkingSteps?: ThinkingStep[]
  thinkingExpanded?: boolean
  format?: 'table' | 'report' | 'bullet' | 'chart'
  formatVariants?: Record<string, string>
  charts?: Array<{ echarts_option?: any; chart_type?: string; title?: string }>
  tables?: Array<{ columns: string[]; data: Record<string, any>[] }>
  createdAt: number
  recordId?: string  // 后端 AnalysisRecord.id，用于删除操作
}

export type OutputFormat = 'table' | 'report' | 'bullet' | 'chart'

/** 多表确认候选 */
export interface TableCandidate {
  id: string
  name: string
  purpose: string
  row_count: number
  columns: Array<{ name: string; dtype: string }>
  score: number
}

interface ChatState {
  messages: ChatMessage[]
  isStreaming: boolean
  isHistory: boolean
  currentSessionId: string | null
  addMessage: (msg: ChatMessage) => void
  updateMessage: (id: string, patch: Partial<ChatMessage>) => void
  removeMessage: (id: string) => void
  clearMessages: () => void
  setStreaming: (v: boolean) => void
  loadSession: (sessionId: string) => Promise<void>
}

let idCounter = 0
function genId(): string {
  idCounter++
  return `msg_${Date.now()}_${idCounter}`
}

export function createMessage(partial: Partial<ChatMessage> & { role: ChatMessage['role']; content: string }): ChatMessage {
  return {
    id: genId(),
    createdAt: Date.now(),
    ...partial,
  }
}

interface BackendRecord {
  id: string
  session_id: string
  role: string
  content: string
  msg_type: string
  created_at: string
}

/** 将后端记录重组为消息列表：每次 user chat 开始一轮对话 */
function reconstructMessages(records: BackendRecord[]): ChatMessage[] {
  const msgs: ChatMessage[] = []
  let currentTurn: BackendRecord[] = []

  for (const rec of records) {
    if (rec.msg_type === 'chat' && rec.role === 'user') {
      // 保存上一轮
      if (currentTurn.length > 0) {
        msgs.push(...buildTurn(currentTurn))
      }
      currentTurn = [rec]
    } else {
      currentTurn.push(rec)
    }
  }
  // 最后一批
  if (currentTurn.length > 0) {
    msgs.push(...buildTurn(currentTurn))
  }
  return msgs
}

/** 将一轮对话的 records 转为 user + assistant 两条消息 */
function buildTurn(records: BackendRecord[]): ChatMessage[] {
  const result: ChatMessage[] = []
  let assistantContent = ''
  let charts: ChatMessage['charts'] = undefined
  let tables: ChatMessage['tables'] = undefined
  let formatVariants: Record<string, string> | undefined = undefined
  const thinkingSteps: ThinkingStep[] = []
  let hasError = false
  let errorContent = ''
  let lastRecordId: string | undefined = undefined  // 关联的后端记录 ID

  for (const rec of records) {
    // 解析 content JSON
    let parsed: any = {}
    try { parsed = JSON.parse(rec.content) } catch { parsed = { raw: rec.content } }

    switch (rec.msg_type) {
      case 'chat':
        if (rec.role === 'user') {
          const userContent = typeof parsed === 'string' ? parsed : (parsed.content || parsed.question || '')
          result.push(createMessage({ role: 'user', content: userContent, recordId: rec.id }))
        }
        break
      case 'planning':
        lastRecordId = rec.id
        if (parsed.steps?.length > 0) {
          const desc = parsed.steps.map((s: any, i: number) => `${i + 1}. ${s.description}`).join('\n')
          thinkingSteps.push({ type: 'planning', content: desc })
        }
        break
      case 'step_result':
        lastRecordId = rec.id
        thinkingSteps.push({
          type: 'step_result',
          content: parsed.description || '',
          successCount: (parsed.results || []).filter((r: any) => r.success).length,
          totalCount: (parsed.results || []).length,
        })
        break
      case 'reflecting':
        lastRecordId = rec.id
        if (parsed.notes?.length > 0) {
          thinkingSteps.push({ type: 'reflecting', content: parsed.notes.join('；') })
        }
        break
      case 'done':
        lastRecordId = rec.id
        assistantContent = parsed.final_response || ''
        charts = parsed.charts?.length > 0 ? parsed.charts : undefined
        tables = parsed.tables?.length > 0 ? parsed.tables : undefined
        formatVariants = parsed.format_variants || undefined
        break
      case 'error':
        lastRecordId = rec.id
        hasError = true
        errorContent = parsed.message || '分析过程出错'
        break
    }
  }

  // 构建 assistant 消息
  const cleanContent = cleanBulletContentStatic(assistantContent)
  if (hasError && !cleanContent) {
    result.push(createMessage({
      role: 'assistant',
      content: errorContent,
      msgType: 'error',
      thinkingSteps: thinkingSteps.length > 0 ? thinkingSteps : undefined,
      thinkingExpanded: false,
      recordId: lastRecordId,
    }))
  } else if (cleanContent || charts || tables) {
    result.push(createMessage({
      role: 'assistant',
      content: cleanContent,
      thinkingSteps: thinkingSteps.length > 0 ? thinkingSteps : undefined,
      thinkingExpanded: false,
      charts,
      tables,
      formatVariants,
      format: (charts?.length ?? 0) > 0 ? 'chart' : 'bullet',
      recordId: lastRecordId,
    }))
  }

  return result
}

function cleanBulletContentStatic(raw: string): string {
  return raw
    .split('\n')
    .filter(line => {
      const trimmed = line.trim()
      if (!trimmed) return false
      if (/^\s*\|.*\|\s*$/.test(line)) return false
      if (/^#{1,3}\s/.test(trimmed)) return false
      return true
    })
    .join('\n')
    .replace(/\n{2,}/g, '\n\n')
    .trim()
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  isStreaming: false,
  isHistory: false,
  currentSessionId: null,
  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  updateMessage: (id, patch) =>
    set((s) => ({
      messages: s.messages.map((m) => (m.id === id ? { ...m, ...patch } : m)),
    })),
  clearMessages: () => set({ messages: [], isHistory: false, currentSessionId: null }),
  removeMessage: (id) => set((s) => ({ messages: s.messages.filter((m) => m.id !== id) })),
  setStreaming: (v) => set({ isStreaming: v }),
  loadSession: async (sessionId: string) => {
    try {
      const { data } = await client.get<BackendRecord[]>(`/sessions/${sessionId}`)
      const msgs = reconstructMessages(data)
      set({ messages: msgs, isHistory: true, currentSessionId: sessionId, isStreaming: false })
    } catch {
      set({ messages: [], isHistory: true, currentSessionId: null })
    }
  },
}))
