import { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useDataset, useCommits, useReviewDataset } from '../api/datasets'
import { CommitGraph } from '../components/dataset/CommitGraph'

export default function DatasetView() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: dataset, isLoading } = useDataset(id)
  const commitsQuery = useCommits(id)
  const reviewDataset = useReviewDataset()
  const [reviewError, setReviewError] = useState<string | null>(null)

  const commits = commitsQuery.data?.pages.flatMap(p => p.items) ?? []

  if (isLoading) return <div className="p-6 text-sm text-slate-400">Loading…</div>
  if (!dataset) return null

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
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center gap-2 text-sm text-slate-400 mb-6">
        <Link to={`/projects/${dataset.project_id}/datasets`} className="hover:text-indigo-600">Datasets</Link>
        <span>/</span>
        <span className="text-slate-700 font-medium">{dataset.name}</span>
      </div>

      <div className="flex items-start justify-between mb-4">
        <h2 className="text-xl font-bold text-slate-800">{dataset.name}</h2>
        <div className="flex flex-col items-end gap-1">
          <button
            onClick={startReview}
            disabled={reviewDataset.isPending}
            className="flex items-center gap-2 bg-orange-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-orange-700 disabled:opacity-60"
          >
            {reviewDataset.isPending && (
              <span className="inline-block w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
            )}
            Review in CVAT
          </button>
          {reviewError && <p className="text-xs text-red-600">{reviewError}</p>}
        </div>
      </div>

      <CommitGraph datasetId={id} commits={commits} />

      {commitsQuery.hasNextPage && (
        <button
          onClick={() => commitsQuery.fetchNextPage()}
          disabled={commitsQuery.isFetchingNextPage}
          className="mt-4 w-full border border-slate-300 text-slate-600 py-2 rounded-lg text-sm hover:bg-slate-50 disabled:opacity-60"
        >
          {commitsQuery.isFetchingNextPage ? 'Loading…' : 'Load more commits'}
        </button>
      )}
    </div>
  )
}
