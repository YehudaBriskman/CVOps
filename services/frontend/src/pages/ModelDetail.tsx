import { useParams, Link } from 'react-router-dom'
import { useModel, useWeightsUrl } from '../api/models'

// Base URL of the MLflow tracking UI. When unset, the run id shows as plain
// text (there's no server to link to yet — see the MLflow standup plan).
const MLFLOW_URL = import.meta.env.VITE_MLFLOW_URL as string | undefined

export default function ModelDetail() {
  const { id } = useParams<{ id: string }>()
  const { data: model, isLoading } = useModel(id)
  const { data: weightsUrl } = useWeightsUrl(id)

  if (isLoading) return <div className="p-6 text-sm text-slate-400">Loading…</div>
  if (!model) return null

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-center gap-2 text-sm text-slate-400 mb-6">
        <Link to={`/projects/${model.project_id}/models`} className="hover:text-indigo-600">Models</Link>
        <span>/</span>
        <span className="text-slate-700 font-mono">{id?.slice(0, 8)}</span>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-slate-800">Model</h2>
          {weightsUrl && (
            <a
              href={weightsUrl.url}
              className="text-xs bg-indigo-600 text-white px-3 py-1.5 rounded-lg hover:bg-indigo-700"
            >
              Download weights
            </a>
          )}
        </div>

        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
          <div>
            <dt className="text-xs text-slate-400">Base model</dt>
            <dd className="font-medium text-slate-800 mt-0.5">{model.base_model ?? '—'}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-400">Code version</dt>
            <dd className="font-medium text-slate-800 mt-0.5">{model.code_version ?? '—'}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-400">Created</dt>
            <dd className="font-medium text-slate-800 mt-0.5">{new Date(model.created_at).toLocaleString()}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-400">Trained on commit</dt>
            <dd className="font-medium text-slate-800 mt-0.5 font-mono text-xs">
              {model.trained_on_commit_id?.slice(0, 8) ?? '—'}
            </dd>
          </div>
          {model.mlflow_run_id && (
            <div>
              <dt className="text-xs text-slate-400">MLflow run</dt>
              <dd className="font-medium mt-0.5 font-mono text-xs">
                {MLFLOW_URL ? (
                  <a
                    href={`${MLFLOW_URL}/#/experiments/0/runs/${model.mlflow_run_id}`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-indigo-600 hover:text-indigo-700"
                  >
                    {model.mlflow_run_id.slice(0, 12)} ↗
                  </a>
                ) : (
                  <span className="text-slate-800">{model.mlflow_run_id.slice(0, 12)}</span>
                )}
              </dd>
            </div>
          )}
        </dl>
      </div>

      {model.metrics && Object.keys(model.metrics).length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-4">
          <h3 className="text-sm font-bold text-slate-700 mb-3">Metrics</h3>
          <div className="grid grid-cols-3 gap-3">
            {Object.entries(model.metrics).map(([k, v]) => (
              <div key={k} className="bg-slate-50 rounded-lg px-3 py-2">
                <p className="text-xs text-slate-400 capitalize">{k.replace(/_/g, ' ')}</p>
                <p className="text-lg font-bold text-slate-800">{String(v)}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {model.hyperparams && Object.keys(model.hyperparams).length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <h3 className="text-sm font-bold text-slate-700 mb-3">Hyperparameters</h3>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            {Object.entries(model.hyperparams).map(([k, v]) => (
              <div key={k}>
                <dt className="text-xs text-slate-400 capitalize">{k.replace(/_/g, ' ')}</dt>
                <dd className="font-medium text-slate-800 mt-0.5">{String(v)}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </div>
  )
}
