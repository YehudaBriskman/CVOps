import { useParams, Link, useNavigate } from 'react-router-dom'
import { MOCK_PROJECTS, MOCK_RECENT_RUNS } from '../mock/data'

const STATUS_BADGE: Record<string, string> = {
  running:   'bg-amber-100 text-amber-700',
  completed: 'bg-green-100 text-green-700',
  failed:    'bg-red-100   text-red-700',
}

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm px-5 py-4">
      <p className="text-xs font-medium text-slate-400 uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold text-slate-900 mt-1">
        {typeof value === 'number' ? value.toLocaleString() : value}
      </p>
    </div>
  )
}

export default function Project() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const project = MOCK_PROJECTS.find(p => p.id === id)

  if (!project) {
    return <div className="p-8 text-center text-slate-400">Project not found.</div>
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Breadcrumb + actions */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 text-sm text-slate-400 mb-1">
            <Link to="/projects" className="hover:text-indigo-600 transition-colors">Projects</Link>
            <span>/</span>
            <span className="text-slate-600 font-medium">{project.name}</span>
          </div>
          <p className="text-slate-400 text-sm capitalize">{project.task_type} · created {project.created_at}</p>
        </div>
        <button
          onClick={() => navigate('/workflows/workflow-1')}
          className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors flex items-center gap-1.5"
        >
          ▶ Open Workflow Builder
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Samples"  value={project.sample_count}  />
        <StatCard label="Datasets" value={project.dataset_count} />
        <StatCard label="Runs"     value={project.run_count}     />
        <StatCard label="Models"   value={project.model_count}   />
      </div>

      {/* Recent Runs */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
        <div className="px-5 py-4 border-b border-slate-100">
          <h3 className="text-sm font-semibold text-slate-800">Recent Runs</h3>
        </div>
        <div className="divide-y divide-slate-100">
          {MOCK_RECENT_RUNS.map(run => (
            <Link
              key={run.id}
              to={`/runs/${run.id}`}
              className="flex items-center gap-4 px-5 py-3.5 hover:bg-slate-50 transition-colors"
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-800">{run.workflow_name}</p>
                <p className="text-xs text-slate-400 mt-0.5">
                  {new Date(run.started_at).toLocaleString()} · at step:{' '}
                  <span className="font-medium text-slate-600">{run.step}</span>
                </p>
              </div>
              <span className={`text-xs px-2.5 py-1 rounded-full font-medium capitalize ${STATUS_BADGE[run.status] ?? 'bg-slate-100 text-slate-500'}`}>
                {run.status}
              </span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}
