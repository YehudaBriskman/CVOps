export type RunStep = {
  id: string
  type_key: string
  label: string
  /** Backend status strings vary (succeeded/completed, cancelled/canceled); StatusPill normalizes. */
  status: string
  started_at: string | null
  finished_at: string | null
  duration: string | null
  config: Record<string, unknown> | null
  inputs: Record<string, unknown> | null
  outputs: Record<string, unknown> | null
  metrics: Record<string, unknown> | null
  error: string | null
  cvat_url?: string
}
