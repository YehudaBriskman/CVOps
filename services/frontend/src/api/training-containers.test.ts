import { beforeEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement, type ReactNode } from 'react'

// Mock the axios instance so no network is hit and we can assert request shaping.
const post = vi.fn()
const get = vi.fn()
const patch = vi.fn()
const del = vi.fn()
vi.mock('../lib/client', () => ({
  client: {
    post: (...a: unknown[]) => post(...a),
    get: (...a: unknown[]) => get(...a),
    patch: (...a: unknown[]) => patch(...a),
    delete: (...a: unknown[]) => del(...a),
  },
}))

import {
  useCreateTrainingContainer,
  useUpdateTrainingContainer,
  useDeleteTrainingContainer,
  useValidateTrainingContainer,
  useTrainingContainers,
} from './training-containers'

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return createElement(QueryClientProvider, { client: qc }, children)
}

beforeEach(() => {
  post.mockReset()
  get.mockReset()
  patch.mockReset()
  del.mockReset()
})

describe('useTrainingContainers', () => {
  it('queries the project-scoped list endpoint', async () => {
    get.mockResolvedValue({ data: [] })
    const { result } = renderHook(() => useTrainingContainers('p1'), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(get).toHaveBeenCalledWith('/projects/p1/training-containers')
  })
})

describe('useCreateTrainingContainer', () => {
  it('posts the body to the project-scoped endpoint', async () => {
    post.mockResolvedValue({ data: { id: 'tc1' } })
    const { result } = renderHook(() => useCreateTrainingContainer('p1'), { wrapper })
    const body = { name: 'x', image: 'img', icd_config: { inputs: {} } }
    await result.current.mutateAsync(body)
    expect(post).toHaveBeenCalledWith('/projects/p1/training-containers', body)
  })
})

describe('useUpdateTrainingContainer', () => {
  it('patches the container endpoint', async () => {
    patch.mockResolvedValue({ data: { id: 'tc1' } })
    const { result } = renderHook(() => useUpdateTrainingContainer('tc1', 'p1'), { wrapper })
    await result.current.mutateAsync({ image: 'img:v2' })
    expect(patch).toHaveBeenCalledWith('/training-containers/tc1', { image: 'img:v2' })
  })
})

describe('useDeleteTrainingContainer', () => {
  it('deletes the container endpoint', async () => {
    del.mockResolvedValue({ data: undefined })
    const { result } = renderHook(() => useDeleteTrainingContainer('p1'), { wrapper })
    await result.current.mutateAsync('tc1')
    expect(del).toHaveBeenCalledWith('/training-containers/tc1')
  })
})

describe('useValidateTrainingContainer', () => {
  it('posts the icd_config instance to the validate endpoint', async () => {
    post.mockResolvedValue({ data: { valid: true, errors: [] } })
    const { result } = renderHook(() => useValidateTrainingContainer('tc1'), { wrapper })
    const out = await result.current.mutateAsync({ epochs: 5 })
    expect(post).toHaveBeenCalledWith('/training-containers/tc1/validate', {
      icd_config: { epochs: 5 },
    })
    expect(out).toEqual({ valid: true, errors: [] })
  })
})
