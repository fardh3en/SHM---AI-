/**
 * useAssetInspections — fetches all inspections for a specific asset.
 * Uses the verified GET /api/v1/inspections/asset/{asset_id} endpoint.
 */
import { useQuery } from '@tanstack/react-query'
import { inspectionsApi } from '../api/inspections'

export function useAssetInspections(assetId: string | undefined) {
  return useQuery({
    queryKey: ['asset-inspections', assetId],
    queryFn: () => inspectionsApi.listForAsset(assetId!),
    enabled: Boolean(assetId),
    staleTime: 30_000,
  })
}
