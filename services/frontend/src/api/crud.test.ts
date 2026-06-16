/**
 * Compact coverage for the straightforward CRUD api modules (projects, tags,
 * collections, models, registry, annotations). The richer modules (samples,
 * runs, datasets, data-sources) have their own dedicated specs.
 */
import { renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { API } from '../test/handlers'
import { server } from '../test/server'
import { withQueryClient } from '../test/utils'
import { useCreateProject, useDeleteProject, useProjects, useUpdateProject } from './projects'
import { useApplySampleTags, useCreateTag, useDeleteTag, useTags } from './tags'
import { useCollections, useCreateCollection, useRemoveCollectionSamples } from './collections'
import { useModel, useModels, useWeightsUrl } from './models'
import { useRegistryTypes } from './registry'
import { useAnnotations } from './annotations'

describe('projects api', () => {
  it('useProjects lists, useCreateProject posts the body', async () => {
    let created: unknown = null
    server.use(
      http.get(`${API}/projects/`, () =>
        HttpResponse.json([{ id: 'p1', org_id: 'o1', name: 'A', task_type: 'detection', default_ontology_id: null, default_ingest_workflow_id: null, created_at: '2026-01-01' }]),
      ),
      http.post(`${API}/projects/`, async ({ request }) => {
        created = await request.json()
        return HttpResponse.json({ id: 'p2', org_id: 'o1', name: 'B', task_type: 'detection', default_ontology_id: null, default_ingest_workflow_id: null, created_at: '2026-01-01' })
      }),
    )
    const list = renderHook(() => useProjects(), { wrapper: withQueryClient() })
    await waitFor(() => expect(list.result.current.isSuccess).toBe(true))
    expect(list.result.current.data?.[0].id).toBe('p1')

    const create = renderHook(() => useCreateProject(), { wrapper: withQueryClient() })
    await create.result.current.mutateAsync({ name: 'B', task_type: 'detection' })
    expect(created).toEqual({ name: 'B', task_type: 'detection' })
  })

  it('useUpdateProject patches and useDeleteProject deletes', async () => {
    let patched: unknown = null
    let deleted = false
    server.use(
      http.patch(`${API}/projects/p1`, async ({ request }) => {
        patched = await request.json()
        return HttpResponse.json({ id: 'p1', org_id: 'o1', name: 'X', task_type: 'detection', default_ontology_id: null, default_ingest_workflow_id: null, created_at: '2026-01-01' })
      }),
      http.delete(`${API}/projects/p1`, () => {
        deleted = true
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const upd = renderHook(() => useUpdateProject('p1'), { wrapper: withQueryClient() })
    await upd.result.current.mutateAsync({ default_ingest_workflow_id: null })
    expect(patched).toEqual({ default_ingest_workflow_id: null })

    const del = renderHook(() => useDeleteProject(), { wrapper: withQueryClient() })
    await del.result.current.mutateAsync('p1')
    expect(deleted).toBe(true)
  })
})

describe('tags api', () => {
  it('lists, creates, applies to a sample, and deletes', async () => {
    let applied: unknown = null
    server.use(
      http.get(`${API}/projects/p1/tags`, () =>
        HttpResponse.json([{ id: 't1', project_id: 'p1', name: 'car', color: '#fff', created_at: '2026-01-01' }]),
      ),
      http.post(`${API}/projects/p1/tags`, () =>
        HttpResponse.json({ id: 't2', project_id: 'p1', name: 'bus', color: '#000', created_at: '2026-01-01' }),
      ),
      http.post(`${API}/samples/s1/tags`, async ({ request }) => {
        applied = await request.json()
        return HttpResponse.json({ id: 's1', tags: [] })
      }),
      http.delete(`${API}/tags/t1`, () => new HttpResponse(null, { status: 204 })),
    )
    const list = renderHook(() => useTags('p1'), { wrapper: withQueryClient() })
    await waitFor(() => expect(list.result.current.isSuccess).toBe(true))
    expect(list.result.current.data?.[0].name).toBe('car')

    const create = renderHook(() => useCreateTag('p1'), { wrapper: withQueryClient() })
    expect((await create.result.current.mutateAsync({ name: 'bus' })).id).toBe('t2')

    const apply = renderHook(() => useApplySampleTags('p1'), { wrapper: withQueryClient() })
    await apply.result.current.mutateAsync({ sampleId: 's1', tagIds: ['t1', 't2'] })
    expect(applied).toEqual({ tag_ids: ['t1', 't2'] })

    const del = renderHook(() => useDeleteTag('p1'), { wrapper: withQueryClient() })
    await expect(del.result.current.mutateAsync('t1')).resolves.toBeUndefined()
  })
})

describe('collections api', () => {
  it('lists with pagination and removes samples via DELETE body', async () => {
    let removeBody: unknown = null
    server.use(
      http.get(`${API}/projects/p1/collections`, () =>
        HttpResponse.json({ items: [{ id: 'c1', project_id: 'p1', name: 'set', description: null, created_at: '2026-01-01', sample_count: 3 }], next_cursor: null }),
      ),
      http.post(`${API}/projects/p1/collections`, () =>
        HttpResponse.json({ id: 'c2', project_id: 'p1', name: 'new', description: null, created_at: '2026-01-01', sample_count: 0 }),
      ),
      http.delete(`${API}/collections/c1/samples`, async ({ request }) => {
        removeBody = await request.json()
        return HttpResponse.json({ matched: 2, affected: 2, skipped_ids: [] })
      }),
    )
    const list = renderHook(() => useCollections('p1'), { wrapper: withQueryClient() })
    await waitFor(() => expect(list.result.current.isSuccess).toBe(true))
    expect(list.result.current.data?.pages[0].items[0].sample_count).toBe(3)

    const create = renderHook(() => useCreateCollection('p1'), { wrapper: withQueryClient() })
    expect((await create.result.current.mutateAsync({ name: 'new' })).id).toBe('c2')

    const remove = renderHook(() => useRemoveCollectionSamples('c1'), { wrapper: withQueryClient() })
    await remove.result.current.mutateAsync(['a', 'b'])
    expect(removeBody).toEqual({ sample_ids: ['a', 'b'] })
  })
})

describe('models api', () => {
  it('lists, gets one, and fetches the weights url', async () => {
    server.use(
      http.get(`${API}/projects/p1/models`, () =>
        HttpResponse.json([{ id: 'm1', project_id: 'p1', blob_hash: 'sha256:x', trained_on_commit_id: null, base_model: null, hyperparams: null, metrics: null, code_version: null, mlflow_run_id: null, created_at: '2026-01-01' }]),
      ),
      http.get(`${API}/models/m1`, () =>
        HttpResponse.json({ id: 'm1', project_id: 'p1', blob_hash: 'sha256:x', trained_on_commit_id: null, base_model: null, hyperparams: null, metrics: null, code_version: null, mlflow_run_id: null, created_at: '2026-01-01' }),
      ),
      http.get(`${API}/models/m1/weights-url`, () => HttpResponse.json({ url: 'http://s3/m1.pt' })),
    )
    const list = renderHook(() => useModels('p1'), { wrapper: withQueryClient() })
    await waitFor(() => expect(list.result.current.isSuccess).toBe(true))
    expect(list.result.current.data?.[0].id).toBe('m1')

    const one = renderHook(() => useModel('m1'), { wrapper: withQueryClient() })
    await waitFor(() => expect(one.result.current.isSuccess).toBe(true))

    const url = renderHook(() => useWeightsUrl('m1'), { wrapper: withQueryClient() })
    await waitFor(() => expect(url.result.current.isSuccess).toBe(true))
    expect(url.result.current.data?.url).toBe('http://s3/m1.pt')
  })
})

describe('registry + annotations api', () => {
  it('useRegistryTypes passes the category filter', async () => {
    let seenCategory: string | null = null
    server.use(
      http.get(`${API}/registry/types`, ({ request }) => {
        seenCategory = new URL(request.url).searchParams.get('category')
        return HttpResponse.json([{ type_key: 'step.extract_frames', category: 'step', json_schema: {}, ui_hints: {} }])
      }),
    )
    const { result } = renderHook(() => useRegistryTypes('step'), { wrapper: withQueryClient() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(seenCategory).toBe('step')
    expect(result.current.data?.[0].type_key).toBe('step.extract_frames')
  })

  it('useAnnotations fetches revisions for a sample', async () => {
    server.use(
      http.get(`${API}/samples/s1/annotations`, () =>
        HttpResponse.json([
          { id: 'rev1', sample_id: 's1', ontology_id: 'o1', ontology_version: 1, revision_no: 1, payload: [{ class_key: 'car', geometry: { coords: [0.5, 0.5, 0.2, 0.2] } }], provenance: null, created_at: '2026-01-01' },
        ]),
      ),
    )
    const { result } = renderHook(() => useAnnotations('s1'), { wrapper: withQueryClient() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.[0].payload[0].class_key).toBe('car')
  })
})
