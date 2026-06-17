import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { client } from '../lib/client'

export interface TrainingContainer {
  id: string
  project_id: string
  name: string
  description?: string | null
  image: string
  icd_config?: Record<string, unknown> | null
  icd_schema_version?: string | null
  created_at: string
}

export interface TrainingContainerInput {
  name: string
  description?: string | null
  image: string
  icd_config: Record<string, unknown>
  icd_schema_version?: string | null
}

export interface ValidateResponse {
  valid: boolean
  errors: string[]
}

export function useTrainingContainers(projectId: string | undefined) {
  return useQuery<TrainingContainer[]>({
    queryKey: ['training-containers', projectId],
    queryFn: async () => {
      const { data } = await client.get<TrainingContainer[]>(
        `/projects/${projectId}/training-containers`,
      )
      return data
    },
    enabled: !!projectId,
  })
}

export function useTrainingContainer(id: string | undefined) {
  return useQuery<TrainingContainer>({
    queryKey: ['training-container', id],
    queryFn: async () => {
      const { data } = await client.get<TrainingContainer>(`/training-containers/${id}`)
      return data
    },
    enabled: !!id,
  })
}

export function useCreateTrainingContainer(projectId: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: TrainingContainerInput) => {
      const { data } = await client.post<TrainingContainer>(
        `/projects/${projectId}/training-containers`,
        body,
      )
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['training-containers', projectId] }),
  })
}

export function useUpdateTrainingContainer(id: string, projectId: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: Partial<TrainingContainerInput>) => {
      const { data } = await client.patch<TrainingContainer>(
        `/training-containers/${id}`,
        body,
      )
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['training-containers', projectId] })
      qc.invalidateQueries({ queryKey: ['training-container', id] })
    },
  })
}

export function useDeleteTrainingContainer(projectId: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await client.delete(`/training-containers/${id}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['training-containers', projectId] }),
  })
}

export function useValidateTrainingContainer(id: string) {
  return useMutation({
    mutationFn: async (icd_config: Record<string, unknown>) => {
      const { data } = await client.post<ValidateResponse>(
        `/training-containers/${id}/validate`,
        { icd_config },
      )
      return data
    },
  })
}
