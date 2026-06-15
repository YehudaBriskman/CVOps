import { useQuery } from '@tanstack/react-query'
import { client } from '../lib/client'

export interface ModelVersion {
  id: string
  project_id: string
  blob_hash: string
  trained_on_commit_id: string | null
  base_model: string | null
  hyperparams: Record<string, unknown> | null
  metrics: Record<string, unknown> | null
  code_version: string | null
  mlflow_run_id: string | null
  created_at: string
}

export function useModels(projectId: string | undefined) {
  return useQuery<ModelVersion[]>({
    queryKey: ['models', projectId],
    queryFn: async () => {
      const { data } = await client.get<ModelVersion[]>(`/projects/${projectId}/models`)
      return data
    },
    enabled: !!projectId,
  })
}

export function useModel(id: string | undefined) {
  return useQuery<ModelVersion>({
    queryKey: ['model', id],
    queryFn: async () => {
      const { data } = await client.get<ModelVersion>(`/models/${id}`)
      return data
    },
    enabled: !!id,
  })
}

export function useWeightsUrl(id: string | undefined) {
  return useQuery<{ url: string }>({
    queryKey: ['weights-url', id],
    queryFn: async () => {
      const { data } = await client.get<{ url: string }>(`/models/${id}/weights-url`)
      return data
    },
    enabled: !!id,
    staleTime: 50 * 60 * 1000,
  })
}
