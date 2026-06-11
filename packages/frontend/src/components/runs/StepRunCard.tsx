import { useState } from 'react'
import clsx from 'clsx'
import type { RunStep } from './types'

const STATUS_STYLE: Record<string, { badge: string; dot: string }> = {
  completed: { badge: 'bg-green-100 text-green-700',  dot: 'bg-green-500' },
  running:   { badge: 'bg-amber-100 text-amber-700',  dot: 'bg-amber-400' },
  failed:    { badge: 'bg-red-100   text-red-700',    dot: 'bg-red-500'   },
  pending:   { badge: 'bg-slate-100 text-slate-500',  dot: 'bg-slate-300' },
}

const ACCENT: Record<string, string> = {
  'step.extract_frames':  'bg-blue-500',
  'step.auto_label':      'bg-purple-500',
  'step.human_review':    'bg-orange-500',
  'step.commit_dataset':  'bg-green-600',
  'step.export_yolo':     'bg-yellow-500',
  'step.train':           'bg-red-500',
}

export function StepRunCard({ step, defaultOpen = false }: { step: RunStep; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  const style  = STATUS_STYLE[step.status] ?? STATUS_STYLE['pending']
  const accent = ACCENT[step.type_key] ?? 'bg-slate-400'

  return (
    <div className={clsx(
      'rounded-xl border bg-white shadow-sm overflow-hidden',
      step.status === 'running' ? 'border-amber-300' : 'border-slate-200',
    )}>
      {/* Header row */}
      <button
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-slate-50 transition-colors"
        onClick={() => setOpen(o => !o)}
      >
        <div className={`w-1.5 h-10 rounded-full flex-shrink-0 ${accent}`} />

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-slate-800">{step.label}</span>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${style.badge}`}>
              {step.status}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            {step.duration ?? (step.status === 'pending' ? 'Waiting…' : 'In progress')}
          </p>
        </div>

        <div className={clsx('w-2 h-2 rounded-full flex-shrink-0', style.dot, step.status === 'running' && 'animate-pulse')} />
        <span className="text-slate-400 text-[10px] ml-1">{open ? '▲' : '▼'}</span>
      </button>

      {/* Expanded detail */}
      {open && (
        <div className="border-t border-slate-100 bg-slate-50 px-4 py-4 space-y-4">
          {/* CVAT gate */}
          {step.cvat_url && (
            <div className="p-3 bg-orange-50 border border-orange-200 rounded-lg">
              <p className="text-xs font-semibold text-orange-900 mb-1">Waiting for human review in CVAT</p>
              <a
                href={step.cvat_url}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-orange-600 underline hover:text-orange-800"
              >
                Open CVAT Task →
              </a>
            </div>
          )}

          {/* Outputs */}
          {step.outputs && (
            <div>
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">Outputs</p>
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(step.outputs).map(([k, v]) => (
                  <div key={k} className="bg-white rounded-lg border border-slate-200 px-3 py-2">
                    <p className="text-xs text-slate-400 capitalize">{k.replace(/_/g, ' ')}</p>
                    <p className="text-sm font-bold text-slate-800">{String(v)}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Logs */}
          {step.logs && (
            <div>
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">Logs</p>
              <pre className="text-xs bg-slate-900 text-green-400 rounded-lg p-3 overflow-x-auto leading-relaxed whitespace-pre-wrap">
                {step.logs}
              </pre>
            </div>
          )}

          {!step.logs && !step.outputs && !step.cvat_url && (
            <p className="text-xs text-slate-400 italic">No output yet.</p>
          )}
        </div>
      )}
    </div>
  )
}
