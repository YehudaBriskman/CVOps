import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { client } from '../lib/client'

export interface CvatModel {
  id: string
  name: string
  kind: string
  description: string
}

export function useCvatModels() {
  return useQuery<CvatModel[]>({
    queryKey: ['cvat-models'],
    queryFn: async () => {
      const { data } = await client.get<CvatModel[]>('/cvat/models')
      return data
    },
    staleTime: 30_000,
  })
}

export function useDeleteCvatModel() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (functionId: string) => {
      const { data } = await client.delete<{ deleted: string }>(`/cvat/models/${functionId}`)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cvat-models'] }),
  })
}

export function useDeployCvatModel() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ modelName, file }: { modelName: string; file: File }) => {
      const form = new FormData()
      form.append('file', file)
      const { data } = await client.post<{ function_name: string }>(
        `/cvat/deploy?model_name=${encodeURIComponent(modelName)}`,
        form,
        { headers: { 'Content-Type': 'multipart/form-data' } },
      )
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cvat-models'] }),
  })
}
