import { useParams, Link } from 'react-router-dom'
import { useCommit } from '../api/datasets'
import { CommitStats } from '../components/dataset/CommitStats'

export default function CommitDetail() {
  const { id: datasetId, cid: commitId } = useParams<{ id: string; cid: string }>()
  const { data: commit, isLoading } = useCommit(datasetId, commitId)

  if (isLoading) return <div className="p-6 text-sm text-slate-400">Loading…</div>
  if (!commit) return null

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-center gap-2 text-sm text-slate-400 mb-6">
        <Link to={`/datasets/${datasetId}`} className="hover:text-indigo-600">Dataset</Link>
        <span>/</span>
        <span className="text-slate-700 font-mono">{commitId?.slice(0, 8)}</span>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-4">
        <h2 className="text-lg font-bold text-slate-800 mb-1">
          {commit.message ?? 'Commit'}
        </h2>
        <p className="text-xs text-slate-400">{new Date(commit.created_at).toLocaleString()}</p>

        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm mt-4">
          <div>
            <dt className="text-xs text-slate-400">Ontology version</dt>
            <dd className="font-medium text-slate-800 mt-0.5">v{commit.ontology_version}</dd>
          </div>
          {commit.stats?.sample_count != null && (
            <div>
              <dt className="text-xs text-slate-400">Samples</dt>
              <dd className="font-medium text-slate-800 mt-0.5">{String(commit.stats.sample_count)}</dd>
            </div>
          )}
        </dl>
      </div>

      <CommitStats stats={commit.stats} />
    </div>
  )
}
