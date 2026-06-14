import { useParams, Link } from 'react-router-dom'
import { useDatasets } from '../api/datasets'

export default function Datasets() {
  const { id: projectId } = useParams<{ id: string }>()
  const { data: datasets, isLoading } = useDatasets(projectId)

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center gap-2 text-sm text-slate-400 mb-6">
        <Link to={`/projects/${projectId}`} className="hover:text-indigo-600">Project</Link>
        <span>/</span>
        <span className="text-slate-700 font-medium">Datasets</span>
      </div>

      <h2 className="text-xl font-bold text-slate-800 mb-4">Datasets</h2>

      {isLoading && <div className="text-center py-12 text-slate-400 text-sm">Loading…</div>}

      {datasets && datasets.length === 0 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-10 text-center">
          <p className="text-sm font-medium text-slate-700">No datasets yet</p>
          <p className="text-xs text-slate-400 mt-1">Datasets are created by workflow commit steps</p>
        </div>
      )}

      {datasets && datasets.length > 0 && (
        <div className="space-y-2">
          {datasets.map(d => (
            <Link
              key={d.id}
              to={`/datasets/${d.id}`}
              className="flex items-center justify-between bg-white rounded-xl border border-slate-200 shadow-sm px-5 py-4 hover:border-indigo-300 hover:shadow-md transition-all"
            >
              <div>
                <p className="font-semibold text-slate-800">{d.name}</p>
                <p className="text-xs text-slate-400 mt-0.5">{new Date(d.created_at).toLocaleDateString()}</p>
              </div>
              <span className="text-slate-300 text-lg">›</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
