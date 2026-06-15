import { renderHook } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { API } from '../test/handlers'
import { server } from '../test/server'
import { withQueryClient } from '../test/utils'
import { checkDuplicate, isProcessing, useUploadImages, type DataSource } from './data-sources'

// Deterministic hash so the upload flow doesn't depend on crypto/wasm.
vi.mock('../lib/hash', () => ({ sha256Hex: vi.fn(async () => 'deadbeef') }))

function ds(partial: Partial<DataSource>): DataSource {
  return {
    id: 'x',
    project_id: 'p1',
    type: 'video',
    status: 'pending',
    blob_hash: null,
    external_uri: null,
    metadata: null,
    sample_count: null,
    latest_run_id: null,
    created_at: '2026-01-01',
    ...partial,
  }
}

describe('isProcessing', () => {
  it('treats terminal statuses as done', () => {
    expect(isProcessing(ds({ status: 'ingested' }))).toBe(false)
    expect(isProcessing(ds({ status: 'failed' }))).toBe(false)
  })
  it('treats an uploaded image as done (no frame extraction)', () => {
    expect(isProcessing(ds({ type: 'image', status: 'uploaded' }))).toBe(false)
  })
  it('treats an ingesting video as still processing', () => {
    expect(isProcessing(ds({ type: 'video', status: 'ingesting' }))).toBe(true)
    expect(isProcessing(ds({ type: 'video', status: 'uploaded' }))).toBe(true)
  })
})

describe('checkDuplicate', () => {
  it('posts the blob hash and returns the dedup verdict', async () => {
    let body: unknown = null
    server.use(
      http.post(`${API}/projects/p1/data-sources/check`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ exists: true, in_current_project: false, matches: [] })
      }),
    )
    const res = await checkDuplicate('p1', 'sha256:abc')
    expect(body).toEqual({ blob_hash: 'sha256:abc' })
    expect(res.exists).toBe(true)
    expect(res.in_current_project).toBe(false)
  })
})

describe('useUploadImages', () => {
  beforeEach(() => {
    // jsdom lacks object-URL + real image decoding; stub both.
    URL.createObjectURL = vi.fn(() => 'blob:fake')
    URL.revokeObjectURL = vi.fn()
    class FakeImage {
      onload: (() => void) | null = null
      onerror: (() => void) | null = null
      naturalWidth = 640
      naturalHeight = 480
      set src(_v: string) {
        queueMicrotask(() => this.onload?.())
      }
    }
    vi.stubGlobal('Image', FakeImage)
  })
  afterEach(() => vi.unstubAllGlobals())

  it('hashes, presigns, PUTs, then confirms and returns the result', async () => {
    const putHits: string[] = []
    let confirmBody: { items?: unknown[]; group?: string } | null = null
    server.use(
      http.post(`${API}/projects/p1/image-uploads/presign`, () =>
        HttpResponse.json({
          items: [{ filename: 'a.jpg', blob_hash: 'sha256:deadbeef', put_url: 'http://s3/put/a' }],
        }),
      ),
      http.put('http://s3/put/a', () => {
        putHits.push('a')
        return new HttpResponse(null, { status: 200 })
      }),
      http.post(`${API}/projects/p1/image-uploads/confirm`, async ({ request }) => {
        confirmBody = (await request.json()) as { items?: unknown[]; group?: string }
        return HttpResponse.json({ source_id: 'src1', created: 1, sample_ids: ['s1'] })
      }),
    )

    const file = new File([new Uint8Array([1, 2, 3])], 'a.jpg', { type: 'image/jpeg' })
    const { result } = renderHook(() => useUploadImages('p1'), { wrapper: withQueryClient() })
    const res = await result.current.mutateAsync({ files: [file], group: 'batch-1' })

    expect(res).toEqual({ source_id: 'src1', created: 1, sample_ids: ['s1'] })
    expect(putHits).toEqual(['a'])
    expect(confirmBody!.group).toBe('batch-1')
    expect(confirmBody!.items).toEqual([
      { blob_hash: 'sha256:deadbeef', width: 640, height: 480, content_type: 'image/jpeg', size_bytes: 3 },
    ])
  })

  it('throws when a storage PUT fails', async () => {
    server.use(
      http.post(`${API}/projects/p1/image-uploads/presign`, () =>
        HttpResponse.json({
          items: [{ filename: 'a.jpg', blob_hash: 'sha256:deadbeef', put_url: 'http://s3/put/a' }],
        }),
      ),
      http.put('http://s3/put/a', () => new HttpResponse(null, { status: 403 })),
    )
    const file = new File([new Uint8Array([1])], 'a.jpg', { type: 'image/jpeg' })
    const { result } = renderHook(() => useUploadImages('p1'), { wrapper: withQueryClient() })
    await expect(result.current.mutateAsync({ files: [file] })).rejects.toThrow(/Upload failed: 403/)
  })
})
