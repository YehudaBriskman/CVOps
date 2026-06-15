import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { client } from '../lib/client'
import type { Sample } from './samples'

export interface Tag {
  id: string
  project_id: string
  name: string
  color: string
  created_at: string
}

export function useTags(projectId: string | undefined) {
  return useQuery<Tag[]>({
    queryKey: ['tags', projectId],
    queryFn: async () => {
      const { data } = await client.get<Tag[]>(`/projects/${projectId}/tags`)
      return data
    },
    enabled: !!projectId,
  })
}

export function useCreateTag(projectId: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { name: string; color?: string }) => {
      const { data } = await client.post<Tag>(`/projects/${projectId}/tags`, body)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tags', projectId] }),
  })
}

export function useUpdateTag(projectId: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: { id: string; name?: string; color?: string }) => {
      const { data } = await client.patch<Tag>(`/tags/${vars.id}`, {
        name: vars.name,
        color: vars.color,
      })
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tags', projectId] }),
  })
}

export function useDeleteTag(projectId: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await client.delete(`/tags/${id}`)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tags', projectId] })
      qc.invalidateQueries({ queryKey: ['samples', projectId] })
    },
  })
}

export function useApplySampleTags(projectId: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: { sampleId: string; tagIds: string[] }) => {
      const { data } = await client.post<Sample>(`/samples/${vars.sampleId}/tags`, {
        tag_ids: vars.tagIds,
      })
      return data
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['samples', projectId] })
      qc.invalidateQueries({ queryKey: ['sample', data.id] })
    },
  })
}
