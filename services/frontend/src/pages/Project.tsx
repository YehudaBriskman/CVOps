import { useParams, Link } from 'react-router-dom'
import { useProject } from '../api/projects'
import { useWorkflows } from '../api/workflows'
import { Breadcrumbs, Card, ErrorState, SkeletonList } from '../components/ui'

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
  const { data: project, isLoading, isError, refetch } = useProject(id)
  const { data: workflows } = useWorkflows(id)

  if (isLoading) {
    return (
      <div className="mx-auto max-w-5xl p-6">
        <SkeletonList rows={4} />
      </div>
    )
  }

  if (isError || !project) {
    return (
      <div className="mx-auto max-w-5xl p-6">
        <ErrorState description="Could not load this project." onRetry={() => refetch()} />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-5xl p-6">
      <Breadcrumbs items={[{ label: 'Projects', to: '/projects' }, { label: project.name }]} />

      <div className="mb-6">
        <h2 className="text-xl font-bold text-text-primary">{project.name}</h2>
        <p className="mt-0.5 text-sm capitalize text-text-muted">{project.task_type}</p>
      </div>

      {workflows && workflows.length > 0 && (
        <Card className="mb-6 p-4">
          <p className="mb-3 text-xs font-bold uppercase tracking-wider text-text-muted">Workflows</p>
          <div className="space-y-2">
            {workflows.map((wf) => (
              <Link
                key={wf.id}
                to={`/workflows/${wf.id}`}
                className="flex items-center justify-between rounded-lg px-3 py-2 transition-colors hover:bg-surface-3"
              >
                <span className="text-sm font-medium text-text-secondary">{wf.name}</span>
                <span className="text-xs text-text-muted">v{wf.version}</span>
              </Link>
            ))}
          </div>
        </Card>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {SECTIONS.map((s) => (
          <Link key={s.path} to={`/projects/${id}/${s.path}`}>
            <Card className="p-5 transition-all hover:border-iris hover:shadow-md">
              <p className="text-sm font-semibold text-text-primary">{s.label}</p>
              <p className="mt-1 text-xs text-text-muted">{s.desc}</p>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  )
}
