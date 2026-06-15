import { useParams, Link } from 'react-router-dom'
import { useDatasets } from '../api/datasets'
import { Breadcrumbs, Card, EmptyState, ErrorState, SkeletonList } from '../components/ui'

export default function Datasets() {
  const { id: projectId } = useParams<{ id: string }>()
  const { data: datasets, isLoading, isError, refetch } = useDatasets(projectId)

  return (
    <div className="mx-auto max-w-5xl p-6">
      <Breadcrumbs
        items={[{ label: 'Project', to: `/projects/${projectId}` }, { label: 'Datasets' }]}
      />

      <h2 className="mb-4 text-xl font-bold text-text-primary">Datasets</h2>

      {isLoading && <SkeletonList rows={3} />}

      {isError && (
        <ErrorState description="Could not load datasets for this project." onRetry={() => refetch()} />
      )}

      {datasets && datasets.length === 0 && (
        <EmptyState
          title="No datasets yet"
          description="Datasets are created by workflow commit steps."
        />
      )}

      {datasets && datasets.length > 0 && (
        <div className="space-y-2">
          {datasets.map((d) => (
            <Link key={d.id} to={`/datasets/${d.id}`}>
              <Card className="flex items-center justify-between px-5 py-4 transition-all hover:border-cobalt hover:shadow-md">
                <div>
                  <p className="font-semibold text-text-primary">{d.name}</p>
                  <p className="mt-0.5 text-xs text-text-muted">{new Date(d.created_at).toLocaleDateString()}</p>
                </div>
                <span className="text-lg text-text-muted">›</span>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
