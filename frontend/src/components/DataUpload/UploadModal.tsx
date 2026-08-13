import { useState, useRef } from 'react'
import { Modal, Upload, message, Progress, Button, Space, Tag, Alert } from 'antd'
import { InboxOutlined, WarningOutlined, CloseCircleOutlined } from '@ant-design/icons'
import type { UploadProps, UploadFile } from 'antd'
import client from '../../api/client'
import type { UploadResponse, DataSourceInfo } from '../../api/types'

const { Dragger } = Upload

interface Props {
  open: boolean
  onClose: () => void
  onSuccess: (result: UploadResponse) => void
}

interface FileTask {
  file: File
  status: 'pending' | 'checking' | 'uploading' | 'done' | 'error' | 'cancelled'
  progress: number
  errorMsg?: string
  result?: UploadResponse
}

function UploadModal({ open, onClose, onSuccess }: Props) {
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [tasks, setTasks] = useState<FileTask[]>([])
  const [uploading, setUploading] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const reset = () => {
    setFileList([])
    setTasks([])
    setUploading(false)
    abortRef.current = null
  }

  const handleClose = () => {
    if (uploading) {
      abortRef.current?.abort()
    }
    reset()
    onClose()
  }

  /* 单文件上传核心 */
  const uploadSingle = async (file: File, taskIndex: number, signal: AbortSignal): Promise<UploadResponse | null> => {
    // Step 1: 查重
    setTasks(prev => prev.map((t, i) => i === taskIndex ? { ...t, status: 'checking', progress: 10 } : t))

    const checkForm = new FormData()
    checkForm.append('file', file)
    const { data: checkResult } = await client.post<{
      is_duplicate: boolean
      existing?: DataSourceInfo
    }>('/upload?mode=check', checkForm, {
      headers: { 'Content-Type': 'multipart/form-data' },
      signal,
    })

    // Step 2: 上传（有重复时自动使用 replace 策略）
    setTasks(prev => prev.map((t, i) => i === taskIndex ? { ...t, status: 'uploading', progress: 30 } : t))

    const uploadForm = new FormData()
    uploadForm.append('file', file)
    const { data: uploadResult } = await client.post<UploadResponse>(
      `/upload?mode=${checkResult.is_duplicate ? 'replace' : 'new'}`,
      uploadForm,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        signal,
        onUploadProgress: (e) => {
          if (e.total) {
            const pct = Math.round(30 + (e.loaded / e.total) * 60)
            setTasks(prev => prev.map((t, i) => i === taskIndex ? { ...t, progress: Math.min(pct, 95) } : t))
          }
        },
      },
    )

    setTasks(prev => prev.map((t, i) => i === taskIndex ? { ...t, status: 'done', progress: 100, result: uploadResult } : t))
    return uploadResult
  }

  /* 全部上传 */
  const handleUploadAll = async () => {
    if (fileList.length === 0) {
      message.warning('请先选择文件')
      return
    }

    const rawFiles = fileList
      .map(f => f.originFileObj)
      .filter(Boolean) as File[]

    const initialTasks: FileTask[] = rawFiles.map(f => ({
      file: f,
      status: 'pending',
      progress: 0,
    }))
    setTasks(initialTasks)
    setUploading(true)

    const controller = new AbortController()
    abortRef.current = controller

    let allDone = 0
    const results: UploadResponse[] = []

    for (let i = 0; i < rawFiles.length; i++) {
      if (controller.signal.aborted) break
      try {
        const result = await uploadSingle(rawFiles[i], i, controller.signal)
        if (result) {
          results.push(result)
          allDone++
        }
      } catch (err: any) {
        if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') {
          setTasks(prev => prev.map((t, idx) => idx === i ? { ...t, status: 'cancelled', progress: t.progress } : t))
          break
        }
        setTasks(prev => prev.map((t, idx) => idx === i ? {
          ...t,
          status: 'error',
          progress: t.progress,
          errorMsg: err?.response?.data?.detail || err?.message || '上传失败',
        } : t))
      }
    }

    setUploading(false)
    if (allDone > 0) {
      message.success(`${allDone} 个文件上传成功`)
      results.forEach(r => onSuccess(r))
    }
    if (allDone === rawFiles.length) {
      reset()
      onClose()
    }
  }

  /* 中止上传 */
  const handleAbort = () => {
    abortRef.current?.abort()
    setUploading(false)
    message.info('已中止上传')
  }

  const uploadProps: UploadProps = {
    onRemove: (file) => {
      setFileList(prev => prev.filter(f => f.uid !== file.uid))
    },
    beforeUpload: (file) => {
      const ext = '.' + file.name.split('.').pop()?.toLowerCase()
      if (!['.csv', '.xlsx', '.xls'].includes(ext)) {
        message.error(`${file.name}: 仅支持 CSV、Excel 格式`)
        return Upload.LIST_IGNORE
      }
      setFileList(prev => [...prev, { ...file, uid: file.name + Date.now() } as unknown as UploadFile])
      return false
    },
    fileList,
    multiple: true,
    accept: '.csv,.xlsx,.xls',
    showUploadList: { showRemoveIcon: true },
  }

  const fileTag = (ext: string) => {
    const color = ext === 'csv' ? 'green' : 'blue'
    return <Tag color={color}>{ext.toUpperCase()}</Tag>
  }

  /* 状态标签 */
  const statusTag = (task: FileTask) => {
    switch (task.status) {
      case 'pending': return <Tag>等待中</Tag>
      case 'checking': return <Tag color="processing">检测中...</Tag>
      case 'uploading': return <Tag color="processing">上传中...</Tag>
      case 'done': return <Tag color="success">已完成</Tag>
      case 'error': return <Tag color="error">失败</Tag>
      case 'cancelled': return <Tag color="default">已取消</Tag>
    }
  }

  return (
    <Modal
      title="上传数据文件"
      open={open}
      onCancel={handleClose}
      width={600}
      footer={
        tasks.length > 0 ? (
          <Space>
            {uploading ? (
              <Button danger icon={<CloseCircleOutlined />} onClick={handleAbort}>中止上传</Button>
            ) : (
              <Button onClick={() => { setTasks([]); setFileList([]) }}>重新选择</Button>
            )}
            <Button type="primary" onClick={handleUploadAll} loading={uploading} disabled={fileList.length === 0}>
              {uploading ? '上传中...' : '开始上传'}
            </Button>
          </Space>
        ) : (
          <Space>
            <Button onClick={handleClose}>取消</Button>
            <Button type="primary" onClick={handleUploadAll} disabled={fileList.length === 0}>
              开始上传
            </Button>
          </Space>
        )
      }
    >
      {tasks.length === 0 ? (
        <>
          <Dragger {...uploadProps}>
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
            <p className="ant-upload-text">点击或拖拽文件到此区域（支持多选）</p>
            <p className="ant-upload-hint">支持 CSV、Excel（.xlsx/.xls），单文件最大 100MB</p>
          </Dragger>
          {fileList.length > 0 && (
            <div style={{ marginTop: 12, color: '#8b96a3', fontSize: 12 }}>
              已选择 {fileList.length} 个文件
            </div>
          )}
        </>
      ) : (
        <div style={{ maxHeight: 400, overflowY: 'auto' }}>
          {tasks.map((task, i) => (
            <div key={i} style={{ marginBottom: 16, padding: 12, background: '#111826', borderRadius: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <span style={{ fontSize: 13, fontWeight: 500 }}>
                  {task.file.name}
                  {fileTag(task.file.name.split('.').pop() || '')}
                </span>
                {statusTag(task)}
              </div>
              <Progress
                percent={task.progress}
                size="small"
                status={task.status === 'error' ? 'exception' : task.status === 'done' ? 'success' : 'active'}
                strokeColor={task.status === 'cancelled' ? '#5b6674' : undefined}
              />
              {(task.status === 'error' && task.errorMsg) && (
                <Alert type="error" message={task.errorMsg} style={{ marginTop: 6 }} banner />
              )}
              {task.status === 'cancelled' && (
                <div style={{ color: '#5b6674', fontSize: 12, marginTop: 4 }}>已取消</div>
              )}
            </div>
          ))}
        </div>
      )}
    </Modal>
  )
}

export default UploadModal
