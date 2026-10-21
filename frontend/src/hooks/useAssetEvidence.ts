import { useQuery } from '@tanstack/react-query'
import { evidenceApi, type AssetEvidence } from '../api/evidence'

export function useAssetEvidence(assetId: string | undefined) {
  return useQuery<AssetEvidence[]>({
    queryKey: ['asset-evidence', assetId],
    queryFn: () => evidenceApi.listForAsset(assetId!),
    enabled: Boolean(assetId),
    staleTime: 60_000,
  })
}
