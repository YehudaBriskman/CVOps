import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useSamples } from '../api/samples'
import { SampleGrid } from '../components/dataset/SampleGrid'
import { Badge, ErrorState } from '../components/ui'

export default function SampleBrowser() {
  const { id: projectId } = useParams<{ id: string }>()
  const [params] = useSearchParams()
  const sourceId = params.get('source') ?? undefined

  const { data, isLoading, isError, refetch, hasNextPage, isFetchingNextPage, fetchNextPage } =
    useSamples(projectId, sourceId)

  const totalLoaded = data?.pages.flatMap((p) => p.items).length ?? 0

  return (
    <div className="mx-auto max-w-7xl p-6">
      <nav className="mb-6 flex items-center gap-2 text-sm text-text-muted">
        <Link to={`/projects/${projectId}`} className="hover:text-cobalt">Project</Link>
        <span>/</span>
        <span className="font-medium text-text-secondary">Samples</span>
      </nav>

      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-text-primary">Samples</h2>
          {totalLoaded > 0 && (
            <p className="mt-0.5 text-sm text-text-muted">
              {totalLoaded} frame{totalLoaded === 1 ? '' : 's'} loaded
            </p>
          )}
        </div>
      </div>

      {sourceId && (
        <div className="mb-4 flex items-center gap-2 text-sm">
          <Badge tone="info">Filtered by source {sourceId.slice(0, 8)}…</Badge>
          <Link to={`/projects/${projectId}/samples`} className="text-xs text-text-muted hover:text-text-secondary">
            Clear filter
          </Link>
        </div>
      )}

      {isError ? (
        <ErrorState description="Could not load samples." onRetry={() => refetch()} />
      ) : (
        <SampleGrid
          data={data}
          isLoading={isLoading}
          hasNextPage={hasNextPage}
          isFetchingNextPage={isFetchingNextPage}
          fetchNextPage={fetchNextPage}
        />
      )}
    </div>
  )
}
