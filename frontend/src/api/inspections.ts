/**
 * Inspections API — /api/v1/inspections/*
 * Mirrors InspectionResponse schema from backend/app/schemas/inspection.py
 */
import { apiGet, apiPost, apiPatch } from './client'
import type { PaginatedResponse } from './assets'

export type InspectionStatus = 'pending' | 'processing' | 'completed' | 'failed'
export type InspectionSource = 'image' | 'video' | 'drone' | 'camera_feed' | 'manual'

export interface Inspection {
  id: string
  asset_id: string
  status: InspectionStatus
  source: InspectionSource
  input_path: string | null
  notes: string | null
  defect_count: number
  health_score: number | null
  processing_time_ms: number | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface InspectionCreate {
  asset_id: string
  source?: InspectionSource
  notes?: string
}

export interface InspectionUpdate {
  status?: InspectionStatus
  notes?: string | null
  health_score?: number | null
  defect_count?: number
  processing_time_ms?: number | null
  error_message?: string | null
  input_path?: string | null
}

export interface InspectionComparisonSummary {
  id: string
  date: string
  status: string
  health_score: number | null
  defect_count: number
  defect_classes: string[]
}

export interface InspectionComparisonResponse {
  asset_id: string
  base_inspection: InspectionComparisonSummary
  target_inspection: InspectionComparisonSummary
  health_score_delta: number | null
  defect_count_delta: number
  common_defect_classes: string[]
  new_defect_classes: string[]
  absent_defect_classes: string[]
  total_pixel_area_delta: number | null
  change_summary: string
  engineering_disclosures: string[]
}

export interface SeverityBreakdownItem {
  level: string
  count: number
  description: string
}

export interface FailureModeItem {
  mode: string
  code_reference: string
  risk_level: string
  description: string
}

export interface StructuralAssessmentResponse {
  inspection_id: string
  asset_id: string
  health_score: number | null
  condition_state: string
  assessment_method: string
  service_version: string
  total_defects: number
  severity_breakdown: SeverityBreakdownItem[]
  failure_modes: FailureModeItem[]
  recommended_action: string
  provenance: Record<string, unknown>
  assessed_at: string
  limitations_and_disclosures: string[]
}

export const inspectionsApi = {
  list: (page = 1, pageSize = 20) =>
    apiGet<PaginatedResponse<Inspection>>(
      `/api/v1/inspections/?page=${page}&page_size=${pageSize}`
    ),
  get: (id: string) => apiGet<Inspection>(`/api/v1/inspections/${id}`),
  listForAsset: (assetId: string) =>
    apiGet<Inspection[]>(`/api/v1/inspections/asset/${assetId}`),
  create: (data: InspectionCreate) =>
    apiPost<Inspection>('/api/v1/inspections/', data),
  update: (id: string, data: InspectionUpdate) =>
    apiPatch<Inspection>(`/api/v1/inspections/${id}`, data),
  run: (id: string) =>
    apiPost<Inspection>(`/api/v1/inspections/${id}/run`, {}),
  getAssessment: (inspectionId: string) =>
    apiGet<StructuralAssessmentResponse>(`/api/v1/inspections/${inspectionId}/assessment`),
  compareInspections: (assetId: string, baseId: string, targetId: string) =>
    apiGet<InspectionComparisonResponse>(
      `/api/v1/assets/${assetId}/inspections/compare?base_id=${baseId}&target_id=${targetId}`
    ),
}
