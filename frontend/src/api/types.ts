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

/** 一键分析预设模板 */
export interface PresetTemplate {
  id: string
  name: string
  description: string
  question: string
  role_key: string
}

/** 报告图表 */
export interface ReportChart {
  echarts_option?: any
  chart_type?: string
  title?: string
}

/** 报告数据表 */
export interface ReportTable {
  columns: string[]
  data: Record<string, any>[]
}

/** 定时报告任务 */
export interface ReportSchedule {
  id: string
  name: string
  data_source_id: string
  question: string
  role_key: string
  frequency: string
  time?: string | null
  enabled: boolean
  last_run_at?: string | null
  created_at?: string | null
  updated_at?: string | null
}

/** 分析报告记录 */
export interface AnalysisReport {
  id: string
  schedule_id?: string | null
  data_source_id: string
  title: string
  role_key: string
  question?: string | null
  summary?: string | null
  sections?: string[] | null
  charts?: ReportChart[] | null
  tables?: ReportTable[] | null
  status: string
  error?: string | null
  created_at?: string | null
}

/** 看板指标卡片 */
export interface DashboardKpi {
  key: string
  label: string
  value: number
  unit?: string
  kind?: string
}

/** 看板图表块 */
export interface DashboardChartBlock {
  chart_type: string
  title?: string
  echarts_option: any
}

/** 看板分区（单个数据源） */
export interface DashboardSection {
  data_source_id: string
  name: string
  purpose?: string
  row_count: number
  kpis: DashboardKpi[]
  charts: DashboardChartBlock[]
}

/** 看板经营解读 */
export interface DashboardInsight {
  text: string
  source: string
}

/** 看板生成响应 */
export interface DashboardResponse {
  insight: DashboardInsight
  sections: DashboardSection[]
  errors?: { data_source_id: string; error: string }[]
}

/** 预测解读 */
export interface ForecastInsight {
  text: string
  source: string
}

/** 预测分析响应 */
export interface ForecastResponse {
  metric: string
  metric_label: string
  method: string
  method_label: string
  periods: number
  freq: string
  freq_label: string
  dates: string[]
  actual: (number | null)[]
  forecast: (number | null)[]
  insight: ForecastInsight
}
