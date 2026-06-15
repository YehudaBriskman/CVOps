import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import clsx from 'clsx'
import { useProjectRuns } from '../api/runs'
import type { RunOut } from '../api/runs'
import { STATUS_BADGE } from './RunView'

const FILTERS: { label: string; value?: string }[] = [
  { label: 'All' },
  { label: 'Running', value: 'running' },
  { label: 'Waiting', value: 'waiting' },
  { label: 'Failed', value: 'failed' },
  { label: 'Succeeded', value: 'succeeded' },
]

export default function Runs() {
  const { id: projectId } = useParams<{ id: string }>()
  const [status, setStatus] = useState<string | undefined>(undefined)
  const { data, isLoading, hasNextPage, isFetchingNextPage, fetchNextPage } =
    useProjectRuns(projectId, status)

  const runs: RunOut[] = data?.pages.flatMap(p => p.items) ?? []

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center gap-2 text-sm text-slate-400 mb-6">
        <Link to={`/projects/${projectId}`} className="hover:text-indigo-600">Project</Link>
        <span>/</span>
        <span className="text-slate-700 font-medium">Runs</span>
      </div>

      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold text-slate-800">Runs</h2>
        <div className="flex gap-1.5">
          {FILTERS.map(f => (
            <button
              key={f.label}
              onClick={() => setStatus(f.value)}
              className={clsx(
                'text-xs px-3 py-1.5 rounded-lg border transition-colors',
                status === f.value
                  ? 'bg-indigo-600 text-white border-indigo-600'
                  : 'border-slate-300 text-slate-600 hover:bg-slate-50',
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading && <div className="text-center py-12 text-slate-400 text-sm">Loading…</div>}

      {!isLoading && runs.length === 0 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-10 text-center">
          <p className="text-sm font-medium text-slate-700">No runs yet</p>
          <p className="text-xs text-slate-400 mt-1">Runs appear here when you dispatch a workflow</p>
        </div>
      )}

      {runs.length > 0 && (
        <div className="space-y-2">
          {runs.map(run => (
            <Link
              key={run.id}
              to={`/runs/${run.id}`}
              className="flex items-center justify-between bg-white rounded-xl border border-slate-200 shadow-sm px-5 py-4 hover:border-indigo-300 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_BADGE[run.status] ?? 'bg-slate-100 text-slate-500'}`}>
                  {run.status}
                  {run.status === 'running' && <span className="ml-1 inline-block w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />}
                </span>
                <div>
                  <p className="font-semibold text-slate-800 text-sm">
                    {run.kind} · {run.id.slice(0, 8)}
                  </p>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {new Date(run.created_at).toLocaleString()}
                    {run.attempt > 1 && ` · attempt ${run.attempt}`}
                  </p>
                </div>
              </div>
              <span className="text-slate-300 text-lg">›</span>
            </Link>
          ))}
        </div>
      )}

      {hasNextPage && (
        <button
          onClick={() => fetchNextPage()}
          disabled={isFetchingNextPage}
          className="mt-4 w-full border border-slate-300 text-slate-600 py-2 rounded-lg text-sm hover:bg-slate-50 disabled:opacity-60 transition-colors"
        >
          {isFetchingNextPage ? 'Loading…' : 'Load more'}
        </button>
      )}
    </div>
  )
}
