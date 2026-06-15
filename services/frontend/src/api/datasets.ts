import { useQuery, useMutation, useQueryClient, useInfiniteQuery } from '@tanstack/react-query'
import { client } from '../lib/client'
import type { CursorPage, Sample } from './samples'
import type { RunOut } from './runs'

export interface TrainCommitRequest {
  git_url: string
  entry_point?: string
  branch?: string | null
  hyperparams?: Record<string, string | number | boolean> | null
}

export interface Dataset {
  id: string
  project_id: string
  name: string
  created_at: string
}

export interface Commit {
  id: string
  dataset_id: string
  message: string | null
  stats: Record<string, unknown> | null
  ontology_id: string
  ontology_version: number
  created_at: string
}

export function useDatasets(projectId: string | undefined) {
  return useQuery<Dataset[]>({
    queryKey: ['datasets', projectId],
    queryFn: async () => {
      const { data } = await client.get<Dataset[]>(`/projects/${projectId}/datasets`)
      return data
    },
    enabled: !!projectId,
  })
}

export function useDataset(id: string | undefined) {
  return useQuery<Dataset>({
    queryKey: ['dataset', id],
    queryFn: async () => {
      const { data } = await client.get<Dataset>(`/datasets/${id}`)
      return data
    },
    enabled: !!id,
  })
}

export function useCommits(datasetId: string | undefined) {
  return useInfiniteQuery<CursorPage<Commit>>({
    queryKey: ['commits', datasetId],
    queryFn: async ({ pageParam }) => {
      const params = new URLSearchParams({ limit: '50' })
      if (pageParam) params.set('cursor', pageParam as string)
      const { data } = await client.get<CursorPage<Commit>>(
        `/datasets/${datasetId}/commits?${params}`,
      )
      return data
    },
    initialPageParam: null,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    enabled: !!datasetId,
  })
}

export function useCommit(datasetId: string | undefined, commitId: string | undefined) {
  return useQuery<Commit>({
    queryKey: ['commit', datasetId, commitId],
    queryFn: async () => {
      const { data } = await client.get<Commit>(`/datasets/${datasetId}/commits/${commitId}`)
      return data
    },
    enabled: !!datasetId && !!commitId,
    staleTime: Infinity,
  })
}

/** The samples frozen into a specific commit (cursor-paginated). */
export function useCommitSamples(datasetId: string | undefined, commitId: string | null | undefined) {
  return useInfiniteQuery<CursorPage<Sample>>({
    queryKey: ['commit-samples', datasetId, commitId],
    queryFn: async ({ pageParam }) => {
      const params = new URLSearchParams({ limit: '100' })
      if (pageParam) params.set('cursor', pageParam as string)
      const { data } = await client.get<CursorPage<Sample>>(
        `/datasets/${datasetId}/commits/${commitId}/samples?${params}`,
      )
      return data
    },
    initialPageParam: null,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    enabled: !!datasetId && !!commitId,
  })
}

export function useReviewDataset() {
  return useMutation({
    mutationFn: async (datasetId: string) => {
      const { data } = await client.post<{ run_id: string }>(
        `/datasets/${datasetId}/review`,
      )
      return data
    },
  })
}

export function useTrainCommit(datasetId: string | undefined) {
  return useMutation({
    mutationFn: async (body: { commitId: string } & TrainCommitRequest) => {
      const { commitId, ...payload } = body
      const { data } = await client.post<RunOut>(
        `/datasets/${datasetId}/commits/${commitId}/train`,
        payload,
      )
      return data
    },
  })
}

export function useCreateDataset() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { projectId: string; name: string }) => {
      const { data } = await client.post<Dataset>(
        `/projects/${body.projectId}/datasets`,
        { name: body.name },
      )
      return data
    },
    onSuccess: (data) => qc.invalidateQueries({ queryKey: ['datasets', data.project_id] }),
  })
}

export interface CommitFromSamplesResult {
  commit_id: string
  committed_count: number
  skipped_count: number
}

export function useCommitFromSamples() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: {
      datasetId: string
      message?: string
      sample_ids: string[]
      branch_name?: string
      split_strategy?: { train_ratio?: number; val_ratio?: number }
      ontology_id?: string
    }) => {
      const { datasetId, ...body } = vars
      const { data } = await client.post<CommitFromSamplesResult>(
        `/datasets/${datasetId}/commits/from-samples`,
        body,
      )
      return data
    },
    onSuccess: (_d, vars) => qc.invalidateQueries({ queryKey: ['commits', vars.datasetId] }),
  })
}
