/**
 * Detections API — /api/v1/inspections/{inspection_id}/detections
 */
import { apiGet } from './client'

export type DefectType =
  | 'crack'
  | 'spalling'
  | 'corrosion'
  | 'exposed_reinforcement'
  | 'delamination'
  | 'pothole'
  | 'surface_damage'
  | 'unknown'

export interface Detection {
  id: string
  inspection_id: string
  defect_type: DefectType
  confidence: number
  bbox_x1: number
  bbox_y1: number
  bbox_x2: number
  bbox_y2: number
  area_px: number | null
  length_px: number | null
  width_px: number | null
  max_width_px?: number | null
  vertical_extent_px?: number | null
  orientation_deg: number | null
  length_mm?: number | null
  width_mm?: number | null
  max_width_mm?: number | null
  area_mm2?: number | null
  calibration_status?: string
  measurement_status?: string
  depth_status?: string
  depth_mm?: number | null
  unavailability_reasons?: string[]
  tile_x: number | null
  tile_y: number | null
  source_image: string | null
  mask_polygon: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export const detectionsApi = {
  listForInspection: (inspectionId: string) =>
    apiGet<Detection[]>(`/api/v1/inspections/${inspectionId}/detections`),
}
