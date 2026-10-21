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
}
