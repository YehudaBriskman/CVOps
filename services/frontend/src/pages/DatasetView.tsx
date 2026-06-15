import { useParams, Link } from 'react-router-dom'
import { useDataset, useCommits } from '../api/datasets'
import { CommitGraph } from '../components/dataset/CommitGraph'
import { Button, ErrorState, SkeletonList } from '../components/ui'

export default function DatasetView() {
  const { id } = useParams<{ id: string }>()
  const { data: dataset, isLoading, isError, refetch } = useDataset(id)
  const commitsQuery = useCommits(id)

  const commits = commitsQuery.data?.pages.flatMap((p) => p.items) ?? []

  if (isLoading) {
    return (
      <div className="mx-auto max-w-5xl p-6">
        <SkeletonList rows={4} />
      </div>
    )
  }

  if (isError || !dataset) {
    return (
      <div className="mx-auto max-w-5xl p-6">
        <ErrorState description="Could not load this dataset." onRetry={() => refetch()} />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-5xl p-6">
      <nav className="mb-6 flex items-center gap-2 text-sm text-text-muted">
        <Link to={`/projects/${dataset.project_id}/datasets`} className="hover:text-cobalt">Datasets</Link>
        <span>/</span>
        <span className="font-medium text-text-secondary">{dataset.name}</span>
      </nav>

      <h2 className="mb-4 text-xl font-bold text-text-primary">{dataset.name}</h2>

      <CommitGraph datasetId={id} commits={commits} />

      {commitsQuery.hasNextPage && (
        <Button
          variant="secondary"
          className="mt-4 w-full"
          loading={commitsQuery.isFetchingNextPage}
          onClick={() => commitsQuery.fetchNextPage()}
        >
          Load more commits
        </Button>
      )}
    </div>
  )
}
