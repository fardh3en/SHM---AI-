/**
 * Evidence API — /api/v1/assets/{asset_id}/evidence & /api/v1/evidence/{id}
 */
import { apiGet, apiPost } from './client'

export type EvidenceClassification =
  | 'verified_structure'
  | 'comparable_reference'
  | 'synthetic_demo'

export interface AssetEvidence {
  id: string
  asset_id: string
  filename: string
  file_path: string
  thumbnail_path: string | null
  caption: string
  component_description: string | null
  classification: EvidenceClassification
  source_url: string | null
  creator: string | null
  license: string | null
  is_sample: boolean
  created_at: string
  updated_at: string
}

export interface AssetEvidenceCreate {
  asset_id: string
  filename: string
  file_path: string
  caption: string
  component_description?: string
  classification?: EvidenceClassification
  source_url?: string
  creator?: string
  license?: string
  is_sample?: boolean
}

export const evidenceApi = {
  listForAsset: (assetId: string) =>
    apiGet<AssetEvidence[]>(`/api/v1/assets/${assetId}/evidence`),

  get: (evidenceId: string) =>
    apiGet<AssetEvidence>(`/api/v1/evidence/${evidenceId}`),

  create: (assetId: string, data: AssetEvidenceCreate) =>
    apiPost<AssetEvidence>(`/api/v1/assets/${assetId}/evidence`, data),
}
