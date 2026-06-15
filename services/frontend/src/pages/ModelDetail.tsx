import { useParams } from 'react-router-dom'
import { useModel, useWeightsUrl } from '../api/models'
import { Breadcrumbs, Card, ErrorState, SkeletonList } from '../components/ui'

export default function ModelDetail() {
  const { id } = useParams<{ id: string }>()
  const { data: model, isLoading, isError, refetch } = useModel(id)
  const { data: weightsUrl } = useWeightsUrl(id)

  if (isLoading) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <SkeletonList rows={3} />
      </div>
    )
  }

  if (isError || !model) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <ErrorState description="Could not load this model." onRetry={() => refetch()} />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl p-6">
      <Breadcrumbs
        items={[
          { label: 'Models', to: `/projects/${model.project_id}/models` },
          { label: id?.slice(0, 8) ?? '', mono: true },
        ]}
      />

      <Card className="mb-4 p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-bold text-text-primary">Model</h2>
          {weightsUrl && (
            <a
              href={weightsUrl.url}
              className="rounded-lg bg-iris px-3 py-1.5 text-xs text-white transition-colors hover:bg-iris-hover"
            >
              Download weights
            </a>
          )}
        </div>

        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
          <div>
            <dt className="text-xs text-text-muted">Base model</dt>
            <dd className="mt-0.5 font-medium text-text-primary">{model.base_model ?? '—'}</dd>
          </div>
          <div>
            <dt className="text-xs text-text-muted">Code version</dt>
            <dd className="mt-0.5 font-medium text-text-primary">{model.code_version ?? '—'}</dd>
          </div>
          <div>
            <dt className="text-xs text-text-muted">Created</dt>
            <dd className="mt-0.5 font-medium text-text-primary">{new Date(model.created_at).toLocaleString()}</dd>
          </div>
          <div>
            <dt className="text-xs text-text-muted">Trained on commit</dt>
            <dd className="mt-0.5 font-mono text-xs font-medium text-text-primary">
              {model.trained_on_commit_id?.slice(0, 8) ?? '—'}
            </dd>
          </div>
        </dl>
      </Card>

      {model.metrics && Object.keys(model.metrics).length > 0 && (
        <Card className="mb-4 p-6">
          <h3 className="mb-3 text-sm font-bold text-text-secondary">Metrics</h3>
          <div className="grid grid-cols-3 gap-3">
            {Object.entries(model.metrics).map(([k, v]) => (
              <div key={k} className="rounded-lg bg-surface-3 px-3 py-2">
                <p className="text-xs capitalize text-text-muted">{k.replace(/_/g, ' ')}</p>
                <p className="text-lg font-bold text-text-primary">{String(v)}</p>
              </div>
            ))}
          </div>
        </Card>
      )}

      {model.hyperparams && Object.keys(model.hyperparams).length > 0 && (
        <Card className="p-6">
          <h3 className="mb-3 text-sm font-bold text-text-secondary">Hyperparameters</h3>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            {Object.entries(model.hyperparams).map(([k, v]) => (
              <div key={k}>
                <dt className="text-xs capitalize text-text-muted">{k.replace(/_/g, ' ')}</dt>
                <dd className="mt-0.5 font-medium text-text-primary">{String(v)}</dd>
              </div>
            ))}
          </dl>
        </Card>
      )}
    </div>
  )
}
