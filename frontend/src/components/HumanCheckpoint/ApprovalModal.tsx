import { useEffect, useRef } from 'react'
import { Modal, Typography, Space, Tag, Button } from 'antd'
import { ExclamationCircleOutlined, CheckOutlined, CloseOutlined } from '@ant-design/icons'

const { Text, Paragraph } = Typography

interface Props {
  open: boolean
  checkId: string
  action: string
  detail: string
  onApprove: (checkId: string) => void
  onReject: (checkId: string) => void
  timeout?: number
}

function ApprovalModal({ open, checkId, action, detail, onApprove, onReject, timeout = 60000 }: Props) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    // 清理之前的定时器
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }

    if (open && timeout > 0) {
      timerRef.current = setTimeout(() => {
        onReject(checkId)
      }, timeout)
    }

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current)
        timerRef.current = null
      }
    }
  }, [open, timeout, checkId, onReject])

  return (
    <Modal
      title={
        <Space>
          <ExclamationCircleOutlined style={{ color: '#faad14' }} />
          <span>需要您的确认</span>
        </Space>
      }
      open={open}
      onCancel={() => onReject(checkId)}
      footer={
        <Space>
          <Button icon={<CloseOutlined />} onClick={() => onReject(checkId)}>
            取消
          </Button>
          <Button type="primary" icon={<CheckOutlined />} onClick={() => onApprove(checkId)}>
            确认执行
          </Button>
        </Space>
      }
      closable={false}
      maskClosable={false}
    >
      <Paragraph>
        <Tag color="warning">{action}</Tag>
      </Paragraph>
      <Paragraph>
        <Text type="secondary">{detail}</Text>
      </Paragraph>
      <Paragraph type="secondary" style={{ fontSize: 12, marginTop: 16 }}>
        提示：{timeout / 1000} 秒内未响应将自动拒绝
      </Paragraph>
    </Modal>
  )
}

export default ApprovalModal
