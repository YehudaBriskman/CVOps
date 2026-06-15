import { useRun, useRunSSE } from '../../api/runs'
import { StepRunCard } from './StepRunCard'
import type { RunStep } from './types'

interface Props {
  runId: string
}

function stepLabel(key: string) {
  return key.replace('step.', '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

export function RunTimeline({ runId }: Props) {
  const { data: detail } = useRun(runId)
  useRunSSE(runId)

  const steps: RunStep[] = (detail?.steps ?? []).map(s => ({
    id: s.id,
    type_key: s.step_id ?? s.kind ?? '',
    label: stepLabel(s.step_id ?? s.kind ?? ''),
    status: s.status as RunStep['status'],
    started_at: s.started_at,
    finished_at: s.finished_at,
    duration:
      s.started_at && s.finished_at
        ? `${Math.round(
            (new Date(s.finished_at).getTime() - new Date(s.started_at).getTime()) / 1000,
          )}s`
        : null,
    outputs: s.output_refs as RunStep['outputs'],
    logs: null,
    cvat_url: (s.output_refs?.cvat_url as string) ?? undefined,
  }))

  if (steps.length === 0) {
    return (
      <div className="text-center py-8 text-slate-400 text-sm">
        {detail?.run.status === 'pending' ? 'Waiting for steps to start…' : 'No steps'}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {steps.map((step, i) => (
        <StepRunCard key={step.id} step={step} defaultOpen={i === 0} />
      ))}
    </div>
  )
}
