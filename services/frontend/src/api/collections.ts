import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { client } from '../lib/client'
import type { CursorPage, Sample } from './samples'

export interface Collection {
  id: string
  project_id: string
  name: string
  description: string | null
  created_at: string
  sample_count: number | null
}

export interface BulkResult {
  matched: number
  affected: number
  skipped_ids: string[]
}

export function useCollections(projectId: string | undefined) {
  return useInfiniteQuery<CursorPage<Collection>>({
    queryKey: ['collections', projectId],
    queryFn: async ({ pageParam }) => {
      const params = new URLSearchParams({ limit: '100' })
      if (pageParam) params.set('cursor', pageParam as string)
      const { data } = await client.get<CursorPage<Collection>>(
        `/projects/${projectId}/collections?${params}`,
      )
      return data
    },
    initialPageParam: null,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    enabled: !!projectId,
  })
}

export function useCollection(id: string | undefined) {
  return useQuery<Collection>({
    queryKey: ['collection', id],
    queryFn: async () => {
      const { data } = await client.get<Collection>(`/collections/${id}`)
      return data
    },
    enabled: !!id,
  })
}

export function useCollectionSamples(id: string | undefined) {
  return useInfiniteQuery<CursorPage<Sample>>({
    queryKey: ['collection-samples', id],
    queryFn: async ({ pageParam }) => {
      const params = new URLSearchParams({ limit: '50' })
      if (pageParam) params.set('cursor', pageParam as string)
      const { data } = await client.get<CursorPage<Sample>>(
        `/collections/${id}/samples?${params}`,
      )
      return data
    },
    initialPageParam: null,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    enabled: !!id,
  })
}

export function useCreateCollection(projectId: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { name: string; description?: string }) => {
      const { data } = await client.post<Collection>(
        `/projects/${projectId}/collections`,
        body,
      )
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['collections', projectId] }),
  })
}

export function useUpdateCollection(projectId: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: { id: string; name?: string; description?: string }) => {
      const { data } = await client.patch<Collection>(`/collections/${vars.id}`, {
        name: vars.name,
        description: vars.description,
      })
      return data
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['collections', projectId] })
      qc.invalidateQueries({ queryKey: ['collection', data.id] })
    },
  })
}

export function useDeleteCollection(projectId: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await client.delete(`/collections/${id}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['collections', projectId] }),
  })
}

export function useRemoveCollectionSamples(collectionId: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (sampleIds: string[]) => {
      const { data } = await client.request<BulkResult>({
        method: 'DELETE',
        url: `/collections/${collectionId}/samples`,
        data: { sample_ids: sampleIds },
      })
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['collection-samples', collectionId] })
      qc.invalidateQueries({ queryKey: ['collection', collectionId] })
    },
  })
}
