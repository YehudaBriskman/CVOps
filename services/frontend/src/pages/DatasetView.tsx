import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useDataset, useCommits, useReviewDataset } from '../api/datasets'
import { usePinProject } from '../lib/useActiveProject'
import { CommitGraph } from '../components/dataset/CommitGraph'
import { Breadcrumbs, Button, ErrorState, SkeletonList } from '../components/ui'

export default function DatasetView() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: dataset, isLoading, isError, refetch } = useDataset(id)
  const commitsQuery = useCommits(id)
  const reviewDataset = useReviewDataset()
  const [reviewError, setReviewError] = useState<string | null>(null)
  usePinProject(dataset?.project_id)

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

  const startReview = () => {
    if (!id) return
    setReviewError(null)
    reviewDataset.mutate(id, {
      onSuccess: ({ run_id }) => navigate(`/runs/${run_id}`),
      onError: (err: unknown) => {
        const msg = (err as { response?: { data?: { detail?: string } } })
          ?.response?.data?.detail
        setReviewError(msg ?? 'Could not start review')
      },
    })
  }

  return (
    <div className="mx-auto max-w-5xl p-6">
      <Breadcrumbs
        items={[
          { label: 'Datasets', to: `/projects/${dataset.project_id}/datasets` },
          { label: dataset.name },
        ]}
      />

      <div className="flex items-start justify-between mb-4">
        <h2 className="text-xl font-bold text-text-primary">{dataset.name}</h2>
        <div className="flex flex-col items-end gap-1">
          <Button onClick={startReview} loading={reviewDataset.isPending}>
            Review in CVAT
          </Button>
          {reviewError && <p className="text-xs text-error">{reviewError}</p>}
        </div>
      </div>

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
