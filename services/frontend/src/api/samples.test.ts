import { renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { API } from '../test/handlers'
import { server } from '../test/server'
import { withQueryClient } from '../test/utils'
import { useBulkSampleAction, useImageUrl, usePatchSample, useSamples } from './samples'

function sample(id: string) {
  return {
    id,
    project_id: 'p1',
    blob_hash: 'sha256:x',
    source_id: 's1',
    width: 10,
    height: 10,
    frame_index: null,
    perceptual_hash: null,
    metadata: null,
    review_status: 'unreviewed',
    tags: [],
    has_annotations: false,
    latest_revision_id: null,
    created_at: '2026-01-01T00:00:00Z',
  }
}

describe('useSamples', () => {
  it('paginates with the cursor across pages', async () => {
    server.use(
      http.get(`${API}/projects/p1/samples`, ({ request }) => {
        const cursor = new URL(request.url).searchParams.get('cursor')
        return cursor
          ? HttpResponse.json({ items: [sample('b')], next_cursor: null })
          : HttpResponse.json({ items: [sample('a')], next_cursor: 'CURSOR1' })
      }),
    )
    const { result } = renderHook(() => useSamples('p1'), { wrapper: withQueryClient() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.pages[0].items[0].id).toBe('a')
    expect(result.current.hasNextPage).toBe(true)

    result.current.fetchNextPage()
    await waitFor(() => expect(result.current.data?.pages).toHaveLength(2))
    expect(result.current.data?.pages[1].items[0].id).toBe('b')
    expect(result.current.hasNextPage).toBe(false)
  })

  it('forwards filters as query params', async () => {
    let seen: URLSearchParams | null = null
    server.use(
      http.get(`${API}/projects/p1/samples`, ({ request }) => {
        seen = new URL(request.url).searchParams
        return HttpResponse.json({ items: [], next_cursor: null })
      }),
    )
    const { result } = renderHook(
      () => useSamples('p1', { review_status: 'accepted', has_annotations: true, tag_id: 't9' }),
      { wrapper: withQueryClient() },
    )
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(seen!.get('review_status')).toBe('accepted')
    expect(seen!.get('has_annotations')).toBe('true')
    expect(seen!.get('tag_id')).toBe('t9')
    expect(seen!.get('limit')).toBe('50')
  })

  it('is disabled without a projectId', () => {
    const { result } = renderHook(() => useSamples(undefined), { wrapper: withQueryClient() })
    expect(result.current.fetchStatus).toBe('idle')
  })
})

describe('sample mutations', () => {
  it('useBulkSampleAction posts the action body and returns the result', async () => {
    let body: unknown = null
    server.use(
      http.post(`${API}/projects/p1/samples/bulk`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ matched: 2, affected: 2, skipped_ids: [] })
      }),
    )
    const { result } = renderHook(() => useBulkSampleAction('p1'), { wrapper: withQueryClient() })
    const res = await result.current.mutateAsync({
      action: 'set_review_status',
      sample_ids: ['a', 'b'],
      review_status: 'accepted',
    })
    expect(res.affected).toBe(2)
    expect(body).toEqual({ action: 'set_review_status', sample_ids: ['a', 'b'], review_status: 'accepted' })
  })

  it('usePatchSample patches /samples/{id}', async () => {
    let patched: unknown = null
    server.use(
      http.patch(`${API}/samples/a`, async ({ request }) => {
        patched = await request.json()
        return HttpResponse.json(sample('a'))
      }),
    )
    const { result } = renderHook(() => usePatchSample('p1'), { wrapper: withQueryClient() })
    await result.current.mutateAsync({ id: 'a', body: { tag_ids: ['t1'] } })
    expect(patched).toEqual({ tag_ids: ['t1'] })
  })

  it('useImageUrl fetches the presigned url', async () => {
    server.use(
      http.get(`${API}/samples/a/image-url`, () => HttpResponse.json({ url: 'http://s3/a.jpg' })),
    )
    const { result } = renderHook(() => useImageUrl('a'), { wrapper: withQueryClient() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.url).toBe('http://s3/a.jpg')
  })
})
