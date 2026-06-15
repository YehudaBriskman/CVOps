import { useParams, Link } from 'react-router-dom'
import { useModels } from '../api/models'

export default function Models() {
  const { id: projectId } = useParams<{ id: string }>()
  const { data: models, isLoading } = useModels(projectId)

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center gap-2 text-sm text-slate-400 mb-6">
        <Link to={`/projects/${projectId}`} className="hover:text-indigo-600">Project</Link>
        <span>/</span>
        <span className="text-slate-700 font-medium">Models</span>
      </div>

      <h2 className="text-xl font-bold text-slate-800 mb-4">Models</h2>

      {isLoading && <div className="text-center py-12 text-slate-400 text-sm">Loading…</div>}

      {models && models.length === 0 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-10 text-center">
          <p className="text-sm font-medium text-slate-700">No models yet</p>
          <p className="text-xs text-slate-400 mt-1">Models are created by training runs</p>
        </div>
      )}

      {models && models.length > 0 && (
        <div className="space-y-2">
          {models.map(m => (
            <Link
              key={m.id}
              to={`/models/${m.id}`}
              className="flex items-center justify-between bg-white rounded-xl border border-slate-200 shadow-sm px-5 py-4 hover:border-indigo-300 hover:shadow-md transition-all"
            >
              <div>
                <p className="font-semibold text-slate-800 text-sm font-mono">{m.id.slice(0, 8)}…</p>
                <p className="text-xs text-slate-400 mt-0.5">
                  {m.base_model ?? 'Unknown base'} · {new Date(m.created_at).toLocaleDateString()}
                </p>
              </div>
              {m.metrics && (
                <div className="text-right">
                  {Object.entries(m.metrics).slice(0, 2).map(([k, v]) => (
                    <p key={k} className="text-xs text-slate-500">
                      {k}: <span className="font-medium text-slate-700">{String(v)}</span>
                    </p>
                  ))}
                </div>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
