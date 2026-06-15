import { useParams, Link } from 'react-router-dom'
import { useCommit } from '../api/datasets'
import { CommitStats } from '../components/dataset/CommitStats'
import { Card, ErrorState, SkeletonList } from '../components/ui'

export default function CommitDetail() {
  const { id: datasetId, cid: commitId } = useParams<{ id: string; cid: string }>()
  const { data: commit, isLoading, isError, refetch } = useCommit(datasetId, commitId)

  if (isLoading) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <SkeletonList rows={3} />
      </div>
    )
  }

  if (isError || !commit) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <ErrorState description="Could not load this commit." onRetry={() => refetch()} />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl p-6">
      <nav className="mb-6 flex items-center gap-2 text-sm text-text-muted">
        <Link to={`/datasets/${datasetId}`} className="hover:text-cobalt">Dataset</Link>
        <span>/</span>
        <span className="font-mono text-text-secondary">{commitId?.slice(0, 8)}</span>
      </nav>

      <Card className="mb-4 p-6">
        <h2 className="mb-1 text-lg font-bold text-text-primary">{commit.message ?? 'Commit'}</h2>
        <p className="text-xs text-text-muted">{new Date(commit.created_at).toLocaleString()}</p>

        <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
          <div>
            <dt className="text-xs text-text-muted">Ontology version</dt>
            <dd className="mt-0.5 font-medium text-text-primary">v{commit.ontology_version}</dd>
          </div>
          {commit.stats?.sample_count != null && (
            <div>
              <dt className="text-xs text-text-muted">Samples</dt>
              <dd className="mt-0.5 font-medium text-text-primary">{String(commit.stats.sample_count)}</dd>
            </div>
          )}
        </dl>
      </Card>

      <CommitStats stats={commit.stats} />
    </div>
  )
}
