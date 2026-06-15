import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { client } from '../lib/client'

export interface Workflow {
  id: string
  project_id: string
  name: string
  definition: Record<string, unknown>
  version: number
  created_at: string
}

export function useWorkflows(projectId: string | undefined) {
  return useQuery<Workflow[]>({
    queryKey: ['workflows', projectId],
    queryFn: async () => {
      const { data } = await client.get<Workflow[]>(`/projects/${projectId}/workflows`)
      return data
    },
    enabled: !!projectId,
  })
}

export function useWorkflow(id: string | undefined) {
  return useQuery<Workflow>({
    queryKey: ['workflow', id],
    queryFn: async () => {
      const { data } = await client.get<Workflow>(`/workflows/${id}`)
      return data
    },
    enabled: !!id,
  })
}

export function useCreateWorkflow() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: {
      projectId: string
      name: string
      definition: Record<string, unknown>
    }) => {
      const { data } = await client.post<Workflow>(
        `/projects/${body.projectId}/workflows`,
        { name: body.name, definition: body.definition },
      )
      return data
    },
    onSuccess: (data) => qc.invalidateQueries({ queryKey: ['workflows', data.project_id] }),
  })
}

export function useUpdateWorkflow(id: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { name?: string; definition?: Record<string, unknown> }) => {
      const { data } = await client.patch<Workflow>(`/workflows/${id}`, body)
      return data
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['workflow', id] })
      qc.invalidateQueries({ queryKey: ['workflows', data.project_id] })
    },
  })
}

export function useDeleteWorkflow() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await client.delete(`/workflows/${id}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['workflows'] }),
  })
}
