import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { assetsApi, type AssetCreate } from '../api/assets'

export function useAssets(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: ['assets', page, pageSize],
    queryFn: () => assetsApi.list(page, pageSize),
  })
}

export function useAsset(id: string | undefined) {
  return useQuery({
    queryKey: ['assets', id],
    queryFn: () => assetsApi.get(id!),
    enabled: Boolean(id),
  })
}

export function useCreateAsset() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: AssetCreate) => assetsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assets'] })
    },
  })
}
