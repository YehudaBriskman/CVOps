import { useState } from 'react'
import clsx from 'clsx'
import type { RunStep } from './types'
import { StatusPill } from '../ui'
import { mlflowRunUrl } from '../../lib/mlflow'

// Category accent colors (saturated dots read on both themes).
const ACCENT: Record<string, string> = {
  'step.extract_frames': 'bg-blue-500',
  'step.auto_label': 'bg-purple-500',
  'step.human_review': 'bg-orange-500',
  'step.commit_dataset': 'bg-green-600',
  'step.export_yolo': 'bg-yellow-500',
  'step.train': 'bg-red-500',
}

function isScalar(v: unknown): v is string | number | boolean {
  return typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean'
}

/** Render a refs/metrics/config record: scalars as a key/value grid, nested values as JSON. */
function DetailSection({ title, values }: { title: string; values: Record<string, unknown> }) {
  const entries = Object.entries(values)
  if (entries.length === 0) return null
  return (
    <div>
      <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-text-muted">{title}</p>
      <div className="grid grid-cols-2 gap-2">
        {entries.map(([k, v]) => (
          <div key={k} className="rounded-lg border border-border bg-surface-2 px-3 py-2">
            <p className="text-xs capitalize text-text-muted">{k.replace(/_/g, ' ')}</p>
            {isScalar(v) ? (
              <p className="break-words font-mono text-sm text-text-primary">{String(v)}</p>
            ) : (
              <pre className="overflow-x-auto whitespace-pre-wrap break-words font-mono text-xs text-text-secondary">
                {JSON.stringify(v, null, 2)}
              </pre>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export function StepRunCard({ step, defaultOpen = false }: { step: RunStep; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  const accent = ACCENT[step.type_key] ?? 'bg-slate-400'

  // The train step writes mlflow_run_id / mlflow_experiment_id onto metrics as
  // soon as the trainer opens its MLflow run, so a link appears mid-run. Pull
  // them out so they show as a link, not raw rows in the metrics grid.
  const mlflowRunId = step.metrics?.mlflow_run_id as string | undefined
  const mlflowUrl = mlflowRunId
    ? mlflowRunUrl(mlflowRunId, (step.metrics?.mlflow_experiment_id as string | undefined) ?? '0')
    : null
  const displayMetrics = step.metrics
    ? Object.fromEntries(
        Object.entries(step.metrics).filter(([k]) => !k.startsWith('mlflow_')),
      )
    : null

  const hasDetail =
    step.error ||
    step.cvat_url ||
    mlflowRunId ||
    (displayMetrics && Object.keys(displayMetrics).length > 0) ||
    (step.outputs && Object.keys(step.outputs).length > 0) ||
    (step.inputs && Object.keys(step.inputs).length > 0) ||
    (step.config && Object.keys(step.config).length > 0)

  return (
    <div
      className={clsx(
        'overflow-hidden rounded-xl border bg-surface-2 shadow-sm',
        step.status === 'running' ? 'border-warning/50' : 'border-border',
      )}
    >
      <button
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-surface-3"
        onClick={() => setOpen((o) => !o)}
      >
        <div className={`h-10 w-1.5 flex-shrink-0 rounded-full ${accent}`} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-text-primary">{step.label}</span>
            <StatusPill status={step.status} />
          </div>
          <p className="mt-0.5 text-xs text-text-muted">
            {step.duration ?? (step.status === 'pending' ? 'Waiting…' : 'In progress')}
          </p>
        </div>
        <span className="ml-1 text-[10px] text-text-muted">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="space-y-4 border-t border-border bg-surface-1 px-4 py-4">
          {step.error && (
            <div className="rounded-lg border border-error/30 bg-error/5 p-3">
              <p className="mb-1 text-[10px] font-bold uppercase tracking-wider text-error">Error</p>
              <pre className="overflow-x-auto whitespace-pre-wrap break-words font-mono text-xs text-error">
                {step.error}
              </pre>
            </div>
          )}

          {step.cvat_url && (
            <div className="rounded-lg border border-warning/30 bg-warning/5 p-3">
              <p className="mb-1 text-xs font-semibold text-text-primary">Waiting for human review in CVAT</p>
              <a
                href={step.cvat_url}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-iris-400 underline hover:opacity-80"
              >
                Open CVAT Task →
              </a>
            </div>
          )}

          {mlflowRunId && (
            <div className="rounded-lg border border-iris/30 bg-iris/5 p-3">
              <p className="mb-1 text-xs font-semibold text-text-primary">MLflow tracking</p>
              {mlflowUrl ? (
                <a
                  href={mlflowUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="font-mono text-xs text-iris-400 underline hover:opacity-80"
                >
                  Follow this run in MLflow ↗
                </a>
              ) : (
                <span className="font-mono text-xs text-text-secondary">{mlflowRunId.slice(0, 12)}</span>
              )}
            </div>
          )}

          {displayMetrics && Object.keys(displayMetrics).length > 0 && (
            <DetailSection title="Metrics" values={displayMetrics} />
          )}
          {step.outputs && <DetailSection title="Outputs" values={step.outputs} />}
          {step.inputs && <DetailSection title="Resolved inputs" values={step.inputs} />}
          {step.config && <DetailSection title="Config" values={step.config} />}

          {!hasDetail && <p className="text-xs italic text-text-muted">No details yet.</p>}
        </div>
      )}
    </div>
  )
}
