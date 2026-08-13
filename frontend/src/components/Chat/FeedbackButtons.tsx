/**
 * @brief 用户反馈组件 — AI 回答质量评价
 *
 * 在每条 AI 回答底部展示赞/踩按钮，收集反馈用于迭代优化。
 * 使用 localStorage 持久化反馈状态。
 */

import { useState, useCallback } from 'react'
import { Tooltip } from 'antd'
import { LikeOutlined, DislikeOutlined, LikeFilled, DislikeFilled } from '@ant-design/icons'

interface Props {
  messageId: string
  sessionId?: string
}

const STORAGE_KEY_PREFIX = 'msg_feedback_'

function getStoredFeedback(messageId: string): 'like' | 'dislike' | null {
  try {
    const val = localStorage.getItem(STORAGE_KEY_PREFIX + messageId)
    if (val === 'like' || val === 'dislike') return val
  } catch {}
  return null
}

function setStoredFeedback(messageId: string, feedback: 'like' | 'dislike' | null) {
  try {
    if (feedback) {
      localStorage.setItem(STORAGE_KEY_PREFIX + messageId, feedback)
    } else {
      localStorage.removeItem(STORAGE_KEY_PREFIX + messageId)
    }
  } catch {}
}

function FeedbackButtons({ messageId, sessionId: _sessionId }: Props) {
  const [feedback, setFeedback] = useState<'like' | 'dislike' | null>(() => getStoredFeedback(messageId))

  const handleLike = useCallback(() => {
    const next = feedback === 'like' ? null : 'like'
    setFeedback(next)
    setStoredFeedback(messageId, next)
  }, [messageId, feedback])

  const handleDislike = useCallback(() => {
    const next = feedback === 'dislike' ? null : 'dislike'
    setFeedback(next)
    setStoredFeedback(messageId, next)
  }, [messageId, feedback])

  return (
    <div style={{ display: 'flex', gap: 2, marginTop: 10, paddingTop: 6, borderTop: '1px solid #243040' }}>
      <Tooltip title={feedback === 'like' ? '取消' : '回答有帮助'}>
        <span
          onClick={handleLike}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 4,
            padding: '2px 8px', borderRadius: 6, cursor: 'pointer',
            fontSize: 12, color: feedback === 'like' ? '#3b82f6' : '#5b6674',
            background: feedback === 'like' ? '#16233a' : 'transparent',
            transition: 'all 0.15s',
            userSelect: 'none',
          }}
        >
          {feedback === 'like' ? <LikeFilled /> : <LikeOutlined />}
        </span>
      </Tooltip>
      <Tooltip title={feedback === 'dislike' ? '取消' : '回答不准确'}>
        <span
          onClick={handleDislike}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 4,
            padding: '2px 8px', borderRadius: 6, cursor: 'pointer',
            fontSize: 12, color: feedback === 'dislike' ? '#ef4444' : '#5b6674',
            background: feedback === 'dislike' ? '#2a1a1a' : 'transparent',
            transition: 'all 0.15s',
            userSelect: 'none',
          }}
        >
          {feedback === 'dislike' ? <DislikeFilled /> : <DislikeOutlined />}
        </span>
      </Tooltip>
    </div>
  )
}

export default FeedbackButtons
