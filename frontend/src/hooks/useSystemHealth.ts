import { useQuery } from '@tanstack/react-query'
import { systemApi } from '../api/system'

export function useSystemHealth() {
  return useQuery({
    queryKey: ['system', 'health'],
    queryFn: systemApi.health,
    refetchInterval: 60_000, // re-check every minute
    retry: 1,
  })
}

export function useSystemInfo() {
  return useQuery({
    queryKey: ['system', 'info'],
    queryFn: systemApi.info,
  })
}
