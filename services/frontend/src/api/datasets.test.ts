import { renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { API } from '../test/handlers'
import { server } from '../test/server'
import { withQueryClient } from '../test/utils'
import {
  useCommitFromSamples,
  useCommits,
  useCreateDataset,
  useDatasets,
  useReviewDataset,
  useTrainCommit,
} from './datasets'

describe('dataset queries', () => {
  it('useDatasets lists project datasets', async () => {
    server.use(
      http.get(`${API}/projects/p1/datasets`, () =>
        HttpResponse.json([{ id: 'd1', project_id: 'p1', name: 'set', created_at: '2026-01-01' }]),
      ),
    )
    const { result } = renderHook(() => useDatasets('p1'), { wrapper: withQueryClient() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.[0].id).toBe('d1')
  })

  it('useCommits paginates', async () => {
    server.use(
      http.get(`${API}/datasets/d1/commits`, ({ request }) => {
        const cursor = new URL(request.url).searchParams.get('cursor')
        return cursor
          ? HttpResponse.json({ items: [], next_cursor: null })
          : HttpResponse.json({
              items: [
                {
                  id: 'c1',
                  dataset_id: 'd1',
                  message: 'init',
                  stats: null,
                  ontology_id: 'o1',
                  ontology_version: 1,
                  created_at: '2026-01-01',
                },
              ],
              next_cursor: 'C1',
            })
      }),
    )
    const { result } = renderHook(() => useCommits('d1'), { wrapper: withQueryClient() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.pages[0].items[0].id).toBe('c1')
    expect(result.current.hasNextPage).toBe(true)
  })
})

describe('dataset mutations', () => {
  it('useReviewDataset posts to /review and returns run_id', async () => {
    server.use(
      http.post(`${API}/datasets/d1/review`, () => HttpResponse.json({ run_id: 'r42' })),
    )
    const { result } = renderHook(() => useReviewDataset(), { wrapper: withQueryClient() })
    const res = await result.current.mutateAsync('d1')
    expect(res.run_id).toBe('r42')
  })

  it('useCommitFromSamples posts sample ids and returns counts', async () => {
    let body: unknown = null
    server.use(
      http.post(`${API}/datasets/d1/commits/from-samples`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ commit_id: 'c2', committed_count: 3, skipped_count: 1 })
      }),
    )
    const { result } = renderHook(() => useCommitFromSamples(), { wrapper: withQueryClient() })
    const res = await result.current.mutateAsync({
      datasetId: 'd1',
      sample_ids: ['a', 'b', 'c', 'd'],
      message: 'cut',
    })
    expect(res).toEqual({ commit_id: 'c2', committed_count: 3, skipped_count: 1 })
    expect(body).toEqual({ sample_ids: ['a', 'b', 'c', 'd'], message: 'cut' })
  })

  it('useCreateDataset posts the name to the project endpoint', async () => {
    server.use(
      http.post(`${API}/projects/p1/datasets`, () =>
        HttpResponse.json({ id: 'd9', project_id: 'p1', name: 'new', created_at: '2026-01-01' }),
      ),
    )
    const { result } = renderHook(() => useCreateDataset(), { wrapper: withQueryClient() })
    const res = await result.current.mutateAsync({ projectId: 'p1', name: 'new' })
    expect(res.id).toBe('d9')
  })

  it('useTrainCommit posts the train payload to the commit endpoint', async () => {
    let body: unknown = null
    server.use(
      http.post(`${API}/datasets/d1/commits/c1/train`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({
          id: 'r5',
          project_id: 'p1',
          kind: 'workflow',
          status: 'pending',
          attempt: 1,
          input_refs: null,
          output_refs: null,
          config: null,
          metrics: null,
          error: null,
          started_at: null,
          finished_at: null,
          created_at: '2026-01-01',
        })
      }),
    )
    const { result } = renderHook(() => useTrainCommit('d1'), { wrapper: withQueryClient() })
    const res = await result.current.mutateAsync({ commitId: 'c1', git_url: 'http://git/repo' })
    expect(res.id).toBe('r5')
    // commitId is stripped from the body; only the train request payload is sent
    expect(body).toEqual({ git_url: 'http://git/repo' })
  })
})
