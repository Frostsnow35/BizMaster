import { Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'

interface Props {
  columns: string[]
  data: Record<string, any>[]
}

function TableCard({ columns, data }: Props) {
  const tableColumns: ColumnsType<Record<string, any>> = columns.map((col) => ({
    title: col,
    dataIndex: col,
    key: col,
    ellipsis: true,
    sorter: (a: any, b: any) => {
      const va = a[col], vb = b[col]
      if (typeof va === 'number' && typeof vb === 'number') return va - vb
      return String(va).localeCompare(String(vb))
    },
  }))

  return (
    <div style={{ marginBottom: 12, background: '#ffffff', borderRadius: 10, padding: '0 4px',
      boxShadow: '0 1px 2px rgba(0,0,0,0.04)' }}>
      <Table
        columns={tableColumns}
        dataSource={data.map((row, i) => ({ ...row, key: i }))}
        size="small"
        pagination={{ pageSize: 20, showSizeChanger: false }}
        scroll={{ x: 'max-content' }}
      />
    </div>
  )
}

export default TableCard
