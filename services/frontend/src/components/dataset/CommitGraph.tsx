import { Link } from 'react-router-dom'
import type { Commit } from '../../api/datasets'

interface Props {
  datasetId: string | undefined
  commits: Commit[]
}

export function CommitGraph({ datasetId, commits }: Props) {
  if (commits.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-10 text-center">
        <p className="text-sm font-medium text-slate-700">No commits yet</p>
        <p className="text-xs text-slate-400 mt-1">Commits are created by workflow commit steps</p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {commits.map((c, i) => (
        <Link
          key={c.id}
          to={`/datasets/${datasetId}/commits/${c.id}`}
          className="flex items-center gap-4 bg-white rounded-xl border border-slate-200 shadow-sm px-5 py-3 hover:border-indigo-300 hover:shadow-md transition-all"
        >
          <div className="flex flex-col items-center flex-shrink-0">
            <div className="w-3 h-3 rounded-full bg-indigo-500 border-2 border-white ring-1 ring-indigo-300" />
            {i < commits.length - 1 && <div className="w-0.5 h-6 bg-slate-200 mt-0.5" />}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-slate-800 truncate">
              {c.message ?? 'Commit'}
            </p>
            <p className="text-xs text-slate-400 mt-0.5">
              {new Date(c.created_at).toLocaleString()}
              {c.stats?.sample_count != null && ` · ${c.stats.sample_count} samples`}
            </p>
          </div>
          <span className="text-xs font-mono text-slate-400">{c.id.slice(0, 7)}</span>
        </Link>
      ))}
    </div>
  )
}
