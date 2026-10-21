/**
 * Assets API — /api/v1/assets/*
 * Mirrors the verified AssetResponse schema from backend/app/schemas/asset.py
 */
import { apiGet, apiPost, apiPatch, apiDelete } from './client'

export type AssetType =
  | 'bridge' | 'building' | 'tunnel' | 'road' | 'dam' | 'pipeline' | 'other'

export type AssetStatus =
  | 'active' | 'inactive' | 'under_maintenance' | 'decommissioned'

export interface Asset {
  id: string
  name: string
  asset_type: AssetType
  location: string | null
  description: string | null
  status: AssetStatus
  construction_year: number | null
  material: string | null
  design_life_years: number | null
  latest_health_score: number | null
  created_at: string
  updated_at: string
}

export interface AssetCreate {
  name: string
  asset_type?: AssetType
  location?: string
  description?: string
  construction_year?: number
  material?: string
  design_life_years?: number
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

export const assetsApi = {
  list: (page = 1, pageSize = 20) =>
    apiGet<PaginatedResponse<Asset>>(`/api/v1/assets/?page=${page}&page_size=${pageSize}`),
  get: (id: string) => apiGet<Asset>(`/api/v1/assets/${id}`),
  create: (data: AssetCreate) => apiPost<Asset>('/api/v1/assets/', data),
  update: (id: string, data: Partial<AssetCreate & { status: AssetStatus }>) =>
    apiPatch<Asset>(`/api/v1/assets/${id}`, data),
  delete: (id: string) => apiDelete<{ message: string; success: boolean }>(`/api/v1/assets/${id}`),
}
