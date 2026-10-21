import { useQuery } from '@tanstack/react-query'
import { detectionsApi, type Detection } from '../api/detections'

export function useInspectionDetections(inspectionId: string | undefined) {
  return useQuery<Detection[]>({
    queryKey: ['inspection-detections', inspectionId],
    queryFn: () => detectionsApi.listForInspection(inspectionId!),
    enabled: Boolean(inspectionId),
    staleTime: 30_000,
  })
}
