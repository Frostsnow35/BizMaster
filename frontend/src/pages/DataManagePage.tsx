import { useState, useMemo } from 'react'
import { Button, Input, Select } from 'antd'
import { UploadOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons'
import UploadModal from '../components/DataUpload/UploadModal'
import DataSourceList from '../components/DataUpload/DataSourceList'
import FieldMappingModal from '../components/DataUpload/FieldMappingModal'
import { useDataSources } from '../hooks/useDataSources'
import type { UploadResponse, DataSourceInfo } from '../api/types'

/* 平台筛选选项 */
const PLATFORM_OPTIONS = [
  { value: '', label: '全部平台' },
  { value: 'taobao', label: '淘宝' },
  { value: 'pinduoduo', label: '拼多多' },
  { value: 'douyin', label: '抖音' },
  { value: 'jd', label: '京东' },
  { value: 'generic', label: '通用' },
]

/* 类型筛选选项 */
const TYPE_OPTIONS = [
  { value: '', label: '全部类型' },
  { value: '订单', label: '订单类' },
  { value: '客户', label: '客户类' },
  { value: '商品', label: '商品类' },
]

function DataManagePage() {
  const [uploadOpen, setUploadOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [platformFilter, setPlatformFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [fieldMappingDsId, setFieldMappingDsId] = useState<string | null>(null)
  const { dataSources, loading, fetchDataSources, deleteDataSource } = useDataSources()

  const handleUploadSuccess = (_result: UploadResponse) => {
    fetchDataSources()
  }

  // 前端筛选
  const filteredData = useMemo(() => {
    let result: DataSourceInfo[] = dataSources
    if (search.trim()) {
      const kw = search.trim().toLowerCase()
      result = result.filter((ds) =>
        ds.name.toLowerCase().includes(kw) ||
        (ds.purpose || '').toLowerCase().includes(kw) ||
        (ds.platform_name || '').toLowerCase().includes(kw) ||
        (ds.columns_meta || []).some((c) => c.name.toLowerCase().includes(kw))
      )
    }
    if (platformFilter) {
      result = result.filter((ds) => ds.platform === platformFilter)
    }
    if (typeFilter) {
      result = result.filter((ds) => (ds.purpose || '').includes(typeFilter))
    }
    return result
  }, [dataSources, search, platformFilter, typeFilter])

  return (
    <div>
      {/* 搜索和筛选栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20, gap: 12, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: 8, flex: 1 }}>
          <Input
            placeholder="搜索数据源名称、字段名..."
            prefix={<SearchOutlined style={{ color: '#5b6674' }} />}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            allowClear
            style={{ maxWidth: 280 }}
          />
          <Select
            options={PLATFORM_OPTIONS}
            value={platformFilter}
            onChange={setPlatformFilter}
            style={{ minWidth: 110 }}
          />
          <Select
            options={TYPE_OPTIONS}
            value={typeFilter}
            onChange={setTypeFilter}
            style={{ minWidth: 110 }}
          />
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button icon={<ReloadOutlined />} onClick={fetchDataSources}>
            刷新
          </Button>
          <Button type="primary" icon={<UploadOutlined />} onClick={() => setUploadOpen(true)}>
            上传数据
          </Button>
        </div>
      </div>

      <DataSourceList
        dataSources={filteredData}
        loading={loading}
        onDelete={deleteDataSource}
        onEditMapping={(ds) => setFieldMappingDsId(ds.id)}
      />

      <UploadModal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onSuccess={handleUploadSuccess}
        onConfirmMapping={(dsId) => setFieldMappingDsId(dsId)}
      />

      <FieldMappingModal
        dataSourceId={fieldMappingDsId}
        open={!!fieldMappingDsId}
        onClose={() => setFieldMappingDsId(null)}
        onSaved={() => {
          setFieldMappingDsId(null)
          fetchDataSources()
        }}
      />
    </div>
  )
}

export default DataManagePage
