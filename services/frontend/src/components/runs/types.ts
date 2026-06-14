export type RunStep = {
  id: string
  type_key: string
  label: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  started_at: string | null
  finished_at: string | null
  duration: string | null
  outputs: Record<string, string | number> | null
  logs: string | null
  cvat_url?: string
}
