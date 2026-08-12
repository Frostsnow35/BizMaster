/** 数据源信息 */
export interface DataSourceInfo {
  id: string
  name: string
  file_type?: string
  file_size_kb?: number
  table_name: string
  row_count: number
  columns_meta: ColumnMeta[]
  purpose?: string
  platform?: string
  platform_name?: string
  column_mapping?: Record<string, string>
  file_path?: string
  created_at: string
  updated_at?: string
}

/** 列元信息 */
export interface ColumnMeta {
  name: string
  dtype: string
  null_count: number
  null_ratio?: number
}

/** 上传响应 */
export interface UploadResponse {
  data_source_id: string
  name: string
  table_name: string
  row_count: number
  columns_meta: ColumnMeta[]
  validation_report: ValidationReport
}

/** 校验报告 */
export interface ValidationReport {
  row_count: number
  column_count: number
  column_types: Record<string, string>
  empty_analysis: {
    total_rows: number
    empty_columns: { name: string; null_count: number; null_ratio: number }[]
    overall_empty_rate: number
  }
  outliers: { column: string; outlier_count: number; outlier_ratio: number }[]
  issues: string[]
  overall_score: number
}
