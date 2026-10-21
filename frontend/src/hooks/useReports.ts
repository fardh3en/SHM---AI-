import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { reportsApi, type ReportSummary, type ReportGenerateRequest, type ReportGenerateResponse } from '../api/reports'

export function useReportsList() {
  return useQuery<ReportSummary[]>({
    queryKey: ['reports-list'],
    queryFn: () => reportsApi.list(),
    staleTime: 15_000,
  })
}

export function useGenerateReport() {
  const queryClient = useQueryClient()

  return useMutation<ReportGenerateResponse, Error, ReportGenerateRequest>({
    mutationFn: (data) => reportsApi.generate(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['reports-list'] })
    },
  })
}
