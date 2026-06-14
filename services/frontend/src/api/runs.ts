import { useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { client } from '../lib/client'

export interface RunOut {
  id: string
  project_id: string
  workflow_id?: string
  step_id?: string
  kind: string
  status: string
  attempt: number
  input_refs: Record<string, unknown> | null
  output_refs: Record<string, unknown> | null
  config: Record<string, unknown> | null
  metrics: Record<string, unknown> | null
  error: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string
}

export interface RunDetail {
  run: RunOut
  steps: RunOut[]
}

export interface EventOut {
  id: string
  actor_id: string | null
  entity_type: string
  entity_id: string
  action: string
  payload: Record<string, unknown> | null
  created_at: string
}

const TERMINAL = new Set(['succeeded', 'failed', 'cancelled'])

export function useRun(id: string | undefined) {
  return useQuery<RunDetail>({
    queryKey: ['run', id],
    queryFn: async () => {
      const { data } = await client.get<RunDetail>(`/runs/${id}`)
      return data
    },
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.run?.status
      return status && TERMINAL.has(status) ? false : 3000
    },
  })
}

export function useRunSSE(runId: string | undefined) {
  const qc = useQueryClient()

  useEffect(() => {
    if (!runId) return
    let cancelled = false

    const connect = async () => {
      const token = localStorage.getItem('access_token')
      const base = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'
      try {
        const res = await fetch(`${base}/runs/${runId}/events/stream`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        })
        if (!res.body) return
        const reader = res.body.getReader()
        const dec = new TextDecoder()
        let buf = ''

        while (!cancelled) {
          const { done, value } = await reader.read()
          if (done) break
          buf += dec.decode(value, { stream: true })
          const parts = buf.split('\n\n')
          buf = parts.pop() ?? ''
          for (const chunk of parts) {
            if (chunk.includes('event: done')) {
              qc.invalidateQueries({ queryKey: ['run', runId] })
              return
            }
            const line = chunk.split('\n').find(l => l.startsWith('data: '))
            if (line) {
              qc.invalidateQueries({ queryKey: ['run', runId] })
            }
          }
        }
      } catch {
        // SSE failed — polling fallback via refetchInterval on useRun is active
      }
    }

    connect()
    return () => { cancelled = true }
  }, [runId, qc])
}

export function useCreateRun() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { workflowId: string; params?: Record<string, unknown> }) => {
      const { data } = await client.post<RunOut>(
        `/workflows/${body.workflowId}/runs`,
        { params: body.params ?? {} },
      )
      return data
    },
    onSuccess: (data) => qc.invalidateQueries({ queryKey: ['run', data.id] }),
  })
}

export function useCancelRun() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await client.post(`/runs/${id}/cancel`)
    },
    onSuccess: (_d, id) => qc.invalidateQueries({ queryKey: ['run', id] }),
  })
}

export function useRetryRun() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await client.post<RunOut>(`/runs/${id}/retry`)
      return data
    },
    onSuccess: (data) => qc.invalidateQueries({ queryKey: ['run', data.id] }),
  })
}

export function useResolveGate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { runId: string; stepId: string; resolution: string }) => {
      await client.post(`/runs/${body.runId}/gates/${body.stepId}/resolve`, {
        resolution: body.resolution,
      })
    },
    onSuccess: (_d, vars) => qc.invalidateQueries({ queryKey: ['run', vars.runId] }),
  })
}
