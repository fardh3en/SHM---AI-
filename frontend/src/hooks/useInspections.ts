import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  inspectionsApi,
  type InspectionCreate,
  type InspectionUpdate,
} from '../api/inspections'

export function useInspections(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: ['inspections', page, pageSize],
    queryFn: () => inspectionsApi.list(page, pageSize),
  })
}

export function useInspection(id: string | undefined) {
  return useQuery({
    queryKey: ['inspections', id],
    queryFn: () => inspectionsApi.get(id!),
    enabled: Boolean(id),
  })
}

export function useAssetInspections(assetId: string | undefined) {
  return useQuery({
    queryKey: ['inspections', 'asset', assetId],
    queryFn: () => inspectionsApi.listForAsset(assetId!),
    enabled: Boolean(assetId),
  })
}

export function useCreateInspection() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: InspectionCreate) => inspectionsApi.create(data),
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: ['inspections'] })
      queryClient.invalidateQueries({ queryKey: ['inspections', 'asset', vars.asset_id] })
      queryClient.invalidateQueries({ queryKey: ['asset-inspections', vars.asset_id] })
    },
  })
}

export function useUpdateInspection() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: InspectionUpdate }) =>
      inspectionsApi.update(id, data),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ['inspections'] })
      queryClient.invalidateQueries({ queryKey: ['inspections', updated.id] })
      queryClient.invalidateQueries({ queryKey: ['inspections', 'asset', updated.asset_id] })
      queryClient.invalidateQueries({ queryKey: ['asset-inspections', updated.asset_id] })
    },
  })
}

export function useRunInspection() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => inspectionsApi.run(id),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ['inspections'] })
      queryClient.invalidateQueries({ queryKey: ['inspections', updated.id] })
      queryClient.invalidateQueries({ queryKey: ['inspections', 'asset', updated.asset_id] })
      queryClient.invalidateQueries({ queryKey: ['asset-inspections', updated.asset_id] })
      queryClient.invalidateQueries({ queryKey: ['assets'] })
    },
  })
}
