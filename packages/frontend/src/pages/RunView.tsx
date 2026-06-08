import { useParams, Link } from 'react-router-dom'
import { MOCK_RUN } from '../mock/data'
import { StepRunCard } from '../components/runs/StepRunCard'

const STATUS_STYLE: Record<string, string> = {
  running:   'bg-amber-100  text-amber-700  border-amber-200',
  completed: 'bg-green-100  text-green-700  border-green-200',
  failed:    'bg-red-100    text-red-700    border-red-200',
  pending:   'bg-slate-100  text-slate-600  border-slate-200',
}

export default function RunView() {
  const { id } = useParams<{ id: string }>()
  const run = id === MOCK_RUN.id ? MOCK_RUN : null

  if (!run) {
    return <div className="p-8 text-center text-slate-400">Run not found.</div>
  }

  const completedCount = run.steps.filter(s => s.status === 'completed').length
  const humanStep = run.steps.find(s => s.type_key === 'step.human_review' && s.status === 'running')

  return (
    <div className="p-6 max-w-3xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-slate-400 mb-4">
        <Link to="/projects" className="hover:text-indigo-600 transition-colors">Projects</Link>
        <span>/</span>
        <Link to={`/projects/${run.project_id}`} className="hover:text-indigo-600 transition-colors">
          {run.project_name}
        </Link>
        <span>/</span>
        <span className="text-slate-600 font-medium">Run</span>
      </div>

      {/* Run summary card */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 mb-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-base font-bold text-slate-900">{run.workflow_name}</h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Started {new Date(run.started_at).toLocaleString()}
            </p>
          </div>
          <span className={`text-xs px-3 py-1 rounded-full font-medium border capitalize flex-shrink-0 ${STATUS_STYLE[run.status] ?? STATUS_STYLE['pending']}`}>
            {run.status}
          </span>
        </div>

        {/* Progress bar */}
        <div className="mt-4">
          <div className="flex justify-between text-xs text-slate-400 mb-1.5">
            <span>{completedCount} / {run.steps.length} steps completed</span>
            <span>{Math.round((completedCount / run.steps.length) * 100)}%</span>
          </div>
          <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-indigo-500 rounded-full transition-all duration-500"
              style={{ width: `${(completedCount / run.steps.length) * 100}%` }}
            />
          </div>
        </div>
      </div>

      {/* Gate banner — shown when human review is running */}
      {humanStep && (
        <div className="mb-5 p-4 bg-orange-50 border border-orange-200 rounded-xl flex items-start gap-3">
          <span className="text-orange-500 text-xl mt-0.5 flex-shrink-0">⏸</span>
          <div>
            <p className="text-sm font-semibold text-orange-900">Pipeline paused — waiting for human review</p>
            <p className="text-xs text-orange-700 mt-0.5">
              Annotators need to complete labeling in CVAT before the pipeline continues.
            </p>
            {humanStep.cvat_url && (
              <a
                href={humanStep.cvat_url}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-orange-600 underline mt-1.5 inline-block hover:text-orange-800"
              >
                Open CVAT Task →
              </a>
            )}
          </div>
        </div>
      )}

      {/* Step cards */}
      <div className="space-y-3">
        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Pipeline Steps</p>
        {run.steps.map(step => (
          <StepRunCard
            key={step.id}
            step={step}
            defaultOpen={step.status === 'running' || step.status === 'failed'}
          />
        ))}
      </div>
    </div>
  )
}
