/**
 * Reports API — /api/v1/reports
 */
import { apiGet, apiPost } from './client'

export interface ReportSummary {
  filename: string
  file_path: string
  asset_id: string | null
  inspection_id: string | null
  created_at: string
  size_bytes: number
  format: string
}

export interface ReportGenerateRequest {
  asset_id: string
  inspection_id: string
  format?: 'html' | 'pdf'
}

export interface ReportGenerateResponse {
  report_id: string
  filename: string
  format: string
  created_at: string
  asset_id: string
  asset_name: string
  inspection_id: string
  health_score: number | null
  recommended_action: string
  cost_estimate_low: number
  cost_estimate_high: number
  currency: string
  html_content: string
  pdf_available: boolean
  pdf_filename?: string | null
  notes: string | null
}

export const reportsApi = {
  list: () => apiGet<ReportSummary[]>('/api/v1/reports/'),

  generate: (data: ReportGenerateRequest) =>
    apiPost<ReportGenerateResponse>('/api/v1/reports/generate', data),

  getFileUrl: (filename: string) => `/api/v1/reports/${filename}`,

  getPdfUrl: (filename: string) => `/api/v1/reports/${filename.replace(/\.html$/, '')}/pdf`,
}
