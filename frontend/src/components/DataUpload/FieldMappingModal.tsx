import { useEffect, useState } from 'react'
import { Modal, Select, Tag, Button, Space, Alert, Spin, message, Typography } from 'antd'
import client from '../../api/client'
import type { FieldMappingResponse, FieldMappingRole } from '../../api/types'

const { Text } = Typography

interface Props {
  dataSourceId: string | null
  open: boolean
  onClose: () => void
  onSaved: () => void
}

/* 字段映射确认弹窗：上传后引导用户确认关键字段角色，可跳过 */
function FieldMappingModal({ dataSourceId, open, onClose, onSaved }: Props) {
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [columns, setColumns] = useState<string[]>([])
  const [roles, setRoles] = useState<FieldMappingRole[]>([])
  const [mapping, setMapping] = useState<Record<string, string | null>>({})

  useEffect(() => {
    if (!open || !dataSourceId) return
    let cancelled = false
    setLoading(true)
    client
      .get<FieldMappingResponse>(`/data-sources/${dataSourceId}/field-mapping`)
      .then(({ data }) => {
        if (cancelled) return
        setColumns(data.columns || [])
        setRoles(data.roles || [])
        setMapping(data.mapping || {})
      })
      .catch(() => {
        if (!cancelled) message.error('字段映射信息加载失败')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [open, dataSourceId])

  const handleSave = async () => {
    if (!dataSourceId) return
    setSaving(true)
    try {
      await client.put(`/data-sources/${dataSourceId}/field-mapping`, { mapping })
      message.success('字段映射已保存')
      onSaved()
    } catch {
      message.error('保存失败，请重试')
    } finally {
      setSaving(false)
    }
  }

  const mappedCount = Object.values(mapping).filter(Boolean).length

  return (
    <Modal
      title="确认字段映射"
      open={open}
      onCancel={onClose}
      width={560}
      footer={
        <Space>
          <Button onClick={onClose}>跳过</Button>
          <Button type="primary" onClick={handleSave} loading={saving}>
            保存映射
          </Button>
        </Space>
      }
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="请确认关键字段的角色，用于看板、预测与指标计算的准确识别。"
        description="未匹配的字段可保持「不指定」，后续也可在数据管理中随时修改。"
      />

      {loading ? (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin />
        </div>
      ) : (
        <>
          <div style={{ marginBottom: 8 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              已识别 {mappedCount} / {columns.length} 个关键字段
            </Text>
          </div>
          <div style={{ maxHeight: 360, overflowY: 'auto' }}>
            {columns.map((col) => (
              <div
                key={col}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '6px 0',
                  borderBottom: '1px solid #1c2530',
                }}
              >
                <span style={{ fontSize: 13, color: '#c9d1d9' }}>{col}</span>
                <Select
                  size="small"
                  style={{ width: 200 }}
                  value={mapping[col] ?? ''}
                  onChange={(v) => setMapping((prev) => ({ ...prev, [col]: v || null }))}
                  options={[
                    { value: '', label: '不指定' },
                    ...roles.map((r) => ({ value: r.key, label: r.label })),
                  ]}
                />
              </div>
            ))}
          </div>
          {mappedCount > 0 && (
            <div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {Object.entries(mapping)
                .filter(([, v]) => v)
                .map(([col, roleKey]) => {
                  const role = roles.find((r) => r.key === roleKey)
                  return (
                    <Tag key={col} color="blue" style={{ fontSize: 11 }}>
                      {col} → {role?.label || roleKey}
                    </Tag>
                  )
                })}
            </div>
          )}
        </>
      )}
    </Modal>
  )
}

export default FieldMappingModal
