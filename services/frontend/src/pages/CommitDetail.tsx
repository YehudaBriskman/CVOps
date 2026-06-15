import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useCommit, useTrainCommit } from '../api/datasets'
import { CommitStats } from '../components/dataset/CommitStats'
import { Breadcrumbs, Button, Card, ErrorState, SkeletonList } from '../components/ui'

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

  const inputCls =
    'w-full border border-border-strong bg-surface-2 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-iris'

  return (
    <div
      className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-6"
      onClick={onClose}
    >
      <form
        onClick={e => e.stopPropagation()}
        onSubmit={submit}
        className="bg-surface-2 rounded-xl border border-border shadow-xl p-6 w-full max-w-md"
      >
        <h3 className="text-lg font-bold text-text-primary mb-4">Train this commit</h3>

        <label className="block text-xs text-text-secondary mb-1">Git repository URL</label>
        <input
          autoFocus
          required
          value={gitUrl}
          onChange={e => setGitUrl(e.target.value)}
          placeholder="https://github.com/org/trainer.git"
          className={`${inputCls} mb-3`}
        />

        <div className="grid grid-cols-2 gap-3 mb-3">
          <div>
            <label className="block text-xs text-text-secondary mb-1">Entry point</label>
            <input
              value={entryPoint}
              onChange={e => setEntryPoint(e.target.value)}
              placeholder="train.py"
              className={inputCls}
            />
          </div>
          <div>
            <label className="block text-xs text-text-secondary mb-1">Branch (optional)</label>
            <input
              value={branch}
              onChange={e => setBranch(e.target.value)}
              placeholder="main"
              className={inputCls}
            />
          </div>
        </div>

        <label className="block text-xs text-text-secondary mb-1">Hyperparameters (optional)</label>
        <div className="space-y-2 mb-3">
          {rows.map((row, i) => (
            <div key={i} className="flex gap-2">
              <input
                value={row.key}
                onChange={e => setRow(i, { key: e.target.value })}
                placeholder="epochs"
                className="flex-1 border border-border-strong bg-surface-2 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-iris"
              />
              <input
                value={row.value}
                onChange={e => setRow(i, { value: e.target.value })}
                placeholder="10"
                className="flex-1 border border-border-strong bg-surface-2 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-iris"
              />
            </div>
          ))}
          <button
            type="button"
            onClick={() => setRows([...rows, { key: '', value: '' }])}
            className="text-xs text-iris-400 hover:text-iris"
          >
            + Add hyperparameter
          </button>
        </div>

        {train.isError && (
          <p className="text-xs text-error mb-3">
            {(train.error as Error)?.message ?? 'Failed to start training'}
          </p>
        )}

        <div className="flex justify-end gap-2 mt-4">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={train.isPending} disabled={!gitUrl.trim()}>
            {train.isPending ? 'Starting…' : 'Start training'}
          </Button>
        </div>
      </form>
    </div>
  )
}

export default function CommitDetail() {
  const { id: datasetId, cid: commitId } = useParams<{ id: string; cid: string }>()
  const { data: commit, isLoading, isError, refetch } = useCommit(datasetId, commitId)
  const [trainOpen, setTrainOpen] = useState(false)

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
      <div className="mb-6 flex items-center justify-between">
        <Breadcrumbs
          items={[
            { label: 'Dataset', to: `/datasets/${datasetId}` },
            { label: commitId?.slice(0, 8) ?? '', mono: true },
          ]}
        />
        <Button size="sm" onClick={() => setTrainOpen(true)}>
          Train
        </Button>
      </div>

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
