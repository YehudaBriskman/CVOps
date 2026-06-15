import { useParams, Link } from 'react-router-dom'
import { useRun, useRunSSE, useCancelRun, useRetryRun } from '../api/runs'
import { StepRunCard } from '../components/runs/StepRunCard'
import { GateResolutionBanner } from '../components/runs/GateResolutionBanner'
import type { RunStep } from '../components/runs/types'

export const STATUS_BADGE: Record<string, string> = {
  pending:   'bg-slate-100 text-slate-500',
  running:   'bg-amber-100 text-amber-700',
  succeeded: 'bg-green-100 text-green-700',
  failed:    'bg-red-100 text-red-700',
  cancelled: 'bg-slate-100 text-slate-500',
  waiting:   'bg-orange-100 text-orange-700',
}

function stepLabel(typeKey: string) {
  return typeKey.replace('step.', '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

export default function RunView() {
  const { id } = useParams<{ id: string }>()
  const { data: detail, isLoading } = useRun(id)
  useRunSSE(id)

  const cancelRun = useCancelRun()
  const retryRun = useRetryRun()

  if (isLoading) {
    return <div className="p-6 text-sm text-slate-400">Loading…</div>
  }

  const run = detail?.run
  const steps = detail?.steps ?? []

  const waitingStep = steps.find(s => s.status === 'waiting')

  const stepCards: RunStep[] = steps.map(s => ({
    id: s.id,
    type_key: s.kind === 'step' ? (s.step_id ?? s.kind) : s.kind,
    label: stepLabel(s.step_id ?? s.kind ?? ''),
    status: s.status as RunStep['status'],
    started_at: s.started_at,
    finished_at: s.finished_at,
    duration: s.started_at && s.finished_at
      ? `${Math.round((new Date(s.finished_at).getTime() - new Date(s.started_at).getTime()) / 1000)}s`
      : null,
    outputs: s.output_refs as RunStep['outputs'],
    logs: null,
    // The coordinator nests gate data under output_refs.gate_data; fall back to
    // a top-level cvat_url for any older shape.
    cvat_url: ((s.output_refs?.gate_data as Record<string, unknown> | undefined)?.cvat_url
      ?? s.output_refs?.cvat_url) as string | undefined,
  }))

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-center gap-2 text-sm text-slate-400 mb-4">
        <Link to="/projects" className="hover:text-indigo-600">Projects</Link>
        <span>/</span>
        <span className="text-slate-700 font-medium">Run {id?.slice(0, 8)}</span>
      </div>

      {run && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm px-5 py-4 mb-4 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_BADGE[run.status] ?? 'bg-slate-100 text-slate-500'}`}>
                {run.status}
                {run.status === 'running' && <span className="ml-1 inline-block w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />}
              </span>
              <span className="text-xs text-slate-400">Attempt {run.attempt}</span>
            </div>
            {run.error && (
              <p className="text-xs text-red-600 mt-1">{run.error}</p>
            )}
          </div>
          <div className="flex gap-2">
            {(run.status === 'pending' || run.status === 'running') && (
              <button
                onClick={() => id && cancelRun.mutate(id)}
                className="text-xs border border-slate-300 text-slate-600 px-3 py-1.5 rounded-lg hover:bg-slate-50"
              >
                Cancel
              </button>
            )}
            {(run.status === 'failed' || run.status === 'cancelled') && (
              <button
                onClick={() => id && retryRun.mutate(id)}
                className="text-xs bg-indigo-600 text-white px-3 py-1.5 rounded-lg hover:bg-indigo-700"
              >
                Retry
              </button>
            )}
          </div>
        </div>
      )}

      {waitingStep && id && (
        <GateResolutionBanner
          runId={id}
          stepId={waitingStep.step_id ?? waitingStep.id}
          cvatUrl={((waitingStep.output_refs?.gate_data as Record<string, unknown> | undefined)?.cvat_url
            ?? waitingStep.output_refs?.cvat_url) as string ?? null}
        />
      )}

      {stepCards.length === 0 && run?.status === 'pending' && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-10 text-center">
          <div className="w-6 h-6 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-slate-500">Starting…</p>
        </div>
      )}

      <div className="space-y-3">
        {stepCards.map((step, i) => (
          <StepRunCard key={step.id} step={step} defaultOpen={i === 0} />
        ))}
      </div>
    </div>
  )
}
