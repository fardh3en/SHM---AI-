/**
 * Evidence API — /api/v1/assets/{asset_id}/evidence & /api/v1/evidence/{id}
 */
import { apiGet, apiPost, apiUpload } from './client'

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

export interface EvidenceUploadResponse {
  id?: string | null
  asset_id?: string | null
  filename: string
  original_filename: string
  file_path: string
  content_type: string
  size_bytes: number
}

export const evidenceApi = {
  listForAsset: (assetId: string) =>
    apiGet<AssetEvidence[]>(`/api/v1/assets/${assetId}/evidence`),

  get: (evidenceId: string) =>
    apiGet<AssetEvidence>(`/api/v1/evidence/${evidenceId}`),

  create: (assetId: string, data: AssetEvidenceCreate) =>
    apiPost<AssetEvidence>(`/api/v1/assets/${assetId}/evidence`, data),

  upload: async (
    file: File,
    assetId?: string,
    caption?: string,
    classification?: EvidenceClassification
  ): Promise<EvidenceUploadResponse> => {
    const formData = new FormData()
    formData.append('file', file)
    if (assetId) formData.append('asset_id', assetId)
    if (caption) formData.append('caption', caption)
    if (classification) formData.append('classification', classification)

    return apiUpload<EvidenceUploadResponse>('/api/v1/evidence/upload', formData)
  },
}
