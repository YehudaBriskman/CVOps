import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { client } from '../lib/client'

export interface Sample {
  id: string
  project_id: string
  blob_hash: string
  source_id: string
  width: number
  height: number
  frame_index: number | null
  perceptual_hash: string | null
  metadata: Record<string, unknown> | null
  created_at: string
}

export interface CursorPage<T> {
  items: T[]
  next_cursor: string | null
}

export function useSamples(projectId: string | undefined, sourceId?: string) {
  return useInfiniteQuery<CursorPage<Sample>>({
    queryKey: ['samples', projectId, sourceId],
    queryFn: async ({ pageParam }) => {
      const params = new URLSearchParams({ limit: '50' })
      if (pageParam) params.set('cursor', pageParam as string)
      if (sourceId) params.set('source_id', sourceId)
      const { data } = await client.get<CursorPage<Sample>>(
        `/projects/${projectId}/samples?${params}`,
      )
      return data
    },
    initialPageParam: null,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    enabled: !!projectId,
  })
}

export function useThumbnailUrl(sampleId: string | undefined) {
  return useQuery<{ url: string }>({
    queryKey: ['thumbnail', sampleId],
    queryFn: async () => {
      const { data } = await client.get<{ url: string }>(`/samples/${sampleId}/thumbnail-url`)
      return data
    },
    enabled: !!sampleId,
    staleTime: 50 * 60 * 1000,
  })
}

export function useImageUrl(sampleId: string | undefined) {
  return useQuery<{ url: string }>({
    queryKey: ['image-url', sampleId],
    queryFn: async () => {
      const { data } = await client.get<{ url: string }>(`/samples/${sampleId}/image-url`)
      return data
    },
    enabled: !!sampleId,
    staleTime: 50 * 60 * 1000,
  })
}
