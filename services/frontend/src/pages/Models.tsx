import { useParams, Link } from 'react-router-dom'
import { useModels } from '../api/models'
import { Breadcrumbs, Card, EmptyState, ErrorState, SkeletonList } from '../components/ui'

export default function Models() {
  const { id: projectId } = useParams<{ id: string }>()
  const { data: models, isLoading, isError, refetch } = useModels(projectId)

  return (
    <div className="mx-auto max-w-5xl p-6">
      <Breadcrumbs
        items={[{ label: 'Project', to: `/projects/${projectId}` }, { label: 'Models' }]}
      />

      <h2 className="mb-4 text-xl font-bold text-text-primary">Models</h2>

      {isLoading && <SkeletonList rows={3} />}

      {isError && (
        <ErrorState description="Could not load models for this project." onRetry={() => refetch()} />
      )}

      {models && models.length === 0 && (
        <EmptyState title="No models yet" description="Models are created by training runs." />
      )}

      {models && models.length > 0 && (
        <div className="space-y-2">
          {models.map((m) => (
            <Link key={m.id} to={`/models/${m.id}`}>
              <Card className="flex items-center justify-between px-5 py-4 transition-all hover:border-iris hover:shadow-md">
                <div>
                  <p className="font-mono text-sm font-semibold text-text-primary">{m.id.slice(0, 8)}…</p>
                  <p className="mt-0.5 text-xs text-text-muted">
                    {m.base_model ?? 'Unknown base'} · {new Date(m.created_at).toLocaleDateString()}
                  </p>
                </div>
                {m.metrics && (
                  <div className="text-right">
                    {Object.entries(m.metrics).slice(0, 2).map(([k, v]) => (
                      <p key={k} className="text-xs text-text-muted">
                        {k}: <span className="font-medium text-text-secondary">{String(v)}</span>
                      </p>
                    ))}
                  </div>
                )}
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
