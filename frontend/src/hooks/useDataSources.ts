import { useState, useEffect, useCallback } from 'react'
import client from '../api/client'
import type { DataSourceInfo } from '../api/types'

export function useDataSources() {
  const [dataSources, setDataSources] = useState<DataSourceInfo[]>([])
  const [loading, setLoading] = useState(false)

  const fetchDataSources = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await client.get<DataSourceInfo[]>('/data-sources')
      setDataSources(data)
    } catch (err) {
      console.error('获取数据源列表失败:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  const deleteDataSource = useCallback(async (id: string) => {
    await client.delete(`/data-sources/${id}`)
    setDataSources((prev) => prev.filter((ds) => ds.id !== id))
  }, [])

  useEffect(() => {
    fetchDataSources()
  }, [fetchDataSources])

  return { dataSources, loading, fetchDataSources, deleteDataSource }
}
