import { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useCommit, useTrainCommit } from '../api/datasets'
import { CommitStats } from '../components/dataset/CommitStats'

interface HyperparamRow {
  key: string
  value: string
}

function TrainModal({
  datasetId,
  commitId,
  onClose,
}: {
  datasetId: string
  commitId: string
  onClose: () => void
}) {
  const navigate = useNavigate()
  const train = useTrainCommit(datasetId)
  const [gitUrl, setGitUrl] = useState('')
  const [entryPoint, setEntryPoint] = useState('train.py')
  const [branch, setBranch] = useState('')
  const [rows, setRows] = useState<HyperparamRow[]>([{ key: '', value: '' }])

  const setRow = (i: number, patch: Partial<HyperparamRow>) =>
    setRows(rows.map((r, idx) => (idx === i ? { ...r, ...patch } : r)))

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const hyperparams = Object.fromEntries(
      rows.filter(r => r.key.trim()).map(r => [r.key.trim(), r.value]),
    )
    train.mutate(
      {
        commitId,
        git_url: gitUrl.trim(),
        entry_point: entryPoint.trim() || 'train.py',
        branch: branch.trim() || null,
        hyperparams: Object.keys(hyperparams).length ? hyperparams : null,
      },
      { onSuccess: run => navigate(`/runs/${run.id}`) },
    )
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-6"
      onClick={onClose}
    >
      <form
        onClick={e => e.stopPropagation()}
        onSubmit={submit}
        className="bg-white rounded-xl border border-slate-200 shadow-xl p-6 w-full max-w-md"
      >
        <h3 className="text-lg font-bold text-slate-800 mb-4">Train this commit</h3>

        <label className="block text-xs text-slate-500 mb-1">Git repository URL</label>
        <input
          autoFocus
          required
          value={gitUrl}
          onChange={e => setGitUrl(e.target.value)}
          placeholder="https://github.com/org/trainer.git"
          className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm mb-3 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />

        <div className="grid grid-cols-2 gap-3 mb-3">
          <div>
            <label className="block text-xs text-slate-500 mb-1">Entry point</label>
            <input
              value={entryPoint}
              onChange={e => setEntryPoint(e.target.value)}
              placeholder="train.py"
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">Branch (optional)</label>
            <input
              value={branch}
              onChange={e => setBranch(e.target.value)}
              placeholder="main"
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>

        <label className="block text-xs text-slate-500 mb-1">Hyperparameters (optional)</label>
        <div className="space-y-2 mb-3">
          {rows.map((row, i) => (
            <div key={i} className="flex gap-2">
              <input
                value={row.key}
                onChange={e => setRow(i, { key: e.target.value })}
                placeholder="epochs"
                className="flex-1 border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <input
                value={row.value}
                onChange={e => setRow(i, { value: e.target.value })}
                placeholder="10"
                className="flex-1 border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          ))}
          <button
            type="button"
            onClick={() => setRows([...rows, { key: '', value: '' }])}
            className="text-xs text-indigo-600 hover:text-indigo-700"
          >
            + Add hyperparameter
          </button>
        </div>

        {train.isError && (
          <p className="text-xs text-red-600 mb-3">
            {(train.error as Error)?.message ?? 'Failed to start training'}
          </p>
        )}

        <div className="flex justify-end gap-2 mt-4">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm text-slate-600 hover:bg-slate-100"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={train.isPending || !gitUrl.trim()}
            className="bg-indigo-600 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-60 transition-colors"
          >
            {train.isPending ? 'Starting…' : 'Start training'}
          </button>
        </div>
      </form>
    </div>
  )
}

export default function CommitDetail() {
  const { id: datasetId, cid: commitId } = useParams<{ id: string; cid: string }>()
  const { data: commit, isLoading } = useCommit(datasetId, commitId)
  const [trainOpen, setTrainOpen] = useState(false)

  if (isLoading) return <div className="p-6 text-sm text-slate-400">Loading…</div>
  if (!commit) return null

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <Link to={`/datasets/${datasetId}`} className="hover:text-indigo-600">Dataset</Link>
          <span>/</span>
          <span className="text-slate-700 font-mono">{commitId?.slice(0, 8)}</span>
        </div>
        <button
          onClick={() => setTrainOpen(true)}
          className="text-xs bg-indigo-600 text-white px-3 py-1.5 rounded-lg hover:bg-indigo-700"
        >
          Train
        </button>
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

      {trainOpen && datasetId && commitId && (
        <TrainModal
          datasetId={datasetId}
          commitId={commitId}
          onClose={() => setTrainOpen(false)}
        />
      )}
    </div>
  )
}
