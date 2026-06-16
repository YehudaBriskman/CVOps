import { renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { API } from '../test/handlers'
import { server } from '../test/server'
import { withQueryClient } from '../test/utils'
import {
  useCancelRun,
  useCreateRun,
  useProjectRuns,
  useResolveGate,
  useRetryRun,
  useRun,
} from './runs'

function run(id: string, status = 'running') {
  return {
    id,
    project_id: 'p1',
    kind: 'workflow',
    status,
    attempt: 1,
    input_refs: null,
    output_refs: null,
    config: null,
    metrics: null,
    error: null,
    started_at: null,
    finished_at: null,
    created_at: '2026-01-01T00:00:00Z',
  }
}

describe('useProjectRuns', () => {
  it('passes the status filter and paginates', async () => {
    let seenStatus: string | null = null
    server.use(
      http.get(`${API}/projects/p1/runs`, ({ request }) => {
        const params = new URL(request.url).searchParams
        seenStatus = params.get('status')
        return params.get('cursor')
          ? HttpResponse.json({ items: [run('r2')], next_cursor: null })
          : HttpResponse.json({ items: [run('r1')], next_cursor: 'C1' })
      }),
    )
    const { result } = renderHook(() => useProjectRuns('p1', 'failed'), {
      wrapper: withQueryClient(),
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(seenStatus).toBe('failed')
    expect(result.current.hasNextPage).toBe(true)
    result.current.fetchNextPage()
    await waitFor(() => expect(result.current.data?.pages).toHaveLength(2))
  })
})

describe('useRun', () => {
  it('fetches run detail', async () => {
    server.use(
      http.get(`${API}/runs/r1`, () => HttpResponse.json({ run: run('r1'), steps: [] })),
    )
    const { result } = renderHook(() => useRun('r1'), { wrapper: withQueryClient() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.run.id).toBe('r1')
  })
})

describe('run mutations', () => {
  it('useCreateRun posts params to the workflow runs endpoint', async () => {
    let body: unknown = null
    server.use(
      http.post(`${API}/workflows/w1/runs`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json(run('r9', 'pending'))
      }),
    )
    const { result } = renderHook(() => useCreateRun(), { wrapper: withQueryClient() })
    const res = await result.current.mutateAsync({ workflowId: 'w1', params: { source_id: 's1' } })
    expect(res.id).toBe('r9')
    expect(body).toEqual({ params: { source_id: 's1' } })
  })

  it('useCancelRun hits the cancel endpoint', async () => {
    let hit = false
    server.use(
      http.post(`${API}/runs/r1/cancel`, () => {
        hit = true
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const { result } = renderHook(() => useCancelRun(), { wrapper: withQueryClient() })
    await result.current.mutateAsync('r1')
    expect(hit).toBe(true)
  })

  it('useRetryRun returns the new run', async () => {
    server.use(http.post(`${API}/runs/r1/retry`, () => HttpResponse.json(run('r1', 'pending'))))
    const { result } = renderHook(() => useRetryRun(), { wrapper: withQueryClient() })
    const res = await result.current.mutateAsync('r1')
    expect(res.status).toBe('pending')
  })

  it('useResolveGate posts the resolution to the gate endpoint', async () => {
    let body: unknown = null
    let url = ''
    server.use(
      http.post(`${API}/runs/r1/gates/step5/resolve`, async ({ request }) => {
        url = new URL(request.url).pathname
        body = await request.json()
        return new HttpResponse(null, { status: 200 })
      }),
    )
    const { result } = renderHook(() => useResolveGate(), { wrapper: withQueryClient() })
    await result.current.mutateAsync({ runId: 'r1', stepId: 'step5', resolution: 'accept' })
    expect(url).toBe('/api/v1/runs/r1/gates/step5/resolve')
    expect(body).toEqual({ resolution: 'accept' })
  })
})
