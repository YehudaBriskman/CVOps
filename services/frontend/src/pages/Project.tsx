import { useParams, Link } from 'react-router-dom'
import { useProject } from '../api/projects'
import { useWorkflows } from '../api/workflows'

const SECTIONS = [
  { label: 'Data Sources', path: 'data-sources', desc: 'Uploaded videos and images' },
  { label: 'Samples',      path: 'samples',      desc: 'Extracted frames' },
  { label: 'Datasets',     path: 'datasets',     desc: 'Versioned labeled sets' },
  { label: 'Workflows',    path: 'workflows',    desc: 'Ingest and training pipelines' },
  { label: 'Models',       path: 'models',       desc: 'Trained model versions' },
  { label: 'Settings',     path: 'settings',     desc: 'Project configuration' },
]

export default function Project() {
  const { id } = useParams<{ id: string }>()
  const { data: project, isLoading } = useProject(id)
  const { data: workflows } = useWorkflows(id)

  if (isLoading) {
    return <div className="p-6 text-sm text-slate-400">Loading…</div>
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center gap-2 text-sm text-slate-400 mb-6">
        <Link to="/projects" className="hover:text-indigo-600 transition-colors">Projects</Link>
        <span>/</span>
        <span className="text-slate-700 font-medium">{project?.name ?? id}</span>
      </div>

      <div className="mb-6">
        <h2 className="text-xl font-bold text-slate-800">{project?.name}</h2>
        <p className="text-sm text-slate-400 mt-0.5 capitalize">{project?.task_type}</p>
      </div>

      {workflows && workflows.length > 0 && (
        <div className="mb-6 bg-white rounded-xl border border-slate-200 shadow-sm p-4">
          <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Workflows</p>
          <div className="space-y-2">
            {workflows.map(wf => (
              <Link
                key={wf.id}
                to={`/workflows/${wf.id}`}
                className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-slate-50 transition-colors"
              >
                <span className="text-sm text-slate-700 font-medium">{wf.name}</span>
                <span className="text-xs text-slate-400">v{wf.version}</span>
              </Link>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {SECTIONS.map(s => (
          <Link
            key={s.path}
            to={`/projects/${id}/${s.path}`}
            className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 hover:border-indigo-300 hover:shadow-md transition-all"
          >
            <p className="font-semibold text-slate-800 text-sm">{s.label}</p>
            <p className="text-xs text-slate-400 mt-1">{s.desc}</p>
          </Link>
        ))}
      </div>
    </div>
  )
}
