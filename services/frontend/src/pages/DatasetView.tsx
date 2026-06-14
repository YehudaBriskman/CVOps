import { useParams, Link } from 'react-router-dom'
import { useDataset, useCommits } from '../api/datasets'
import { CommitGraph } from '../components/dataset/CommitGraph'

export default function DatasetView() {
  const { id } = useParams<{ id: string }>()
  const { data: dataset, isLoading } = useDataset(id)
  const commitsQuery = useCommits(id)

  const commits = commitsQuery.data?.pages.flatMap(p => p.items) ?? []

  if (isLoading) return <div className="p-6 text-sm text-slate-400">Loading…</div>
  if (!dataset) return null

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center gap-2 text-sm text-slate-400 mb-6">
        <Link to={`/projects/${dataset.project_id}/datasets`} className="hover:text-indigo-600">Datasets</Link>
        <span>/</span>
        <span className="text-slate-700 font-medium">{dataset.name}</span>
      </div>

      <h2 className="text-xl font-bold text-slate-800 mb-4">{dataset.name}</h2>

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
