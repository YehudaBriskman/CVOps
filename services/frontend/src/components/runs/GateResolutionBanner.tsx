import { useResolveGate } from '../../api/runs'

interface Props {
  runId: string
  stepId: string
  cvatUrl: string | null
}

export function GateResolutionBanner({ runId, stepId, cvatUrl }: Props) {
  const resolve = useResolveGate()

  function handleResolve(resolution: 'approved' | 'rejected') {
    resolve.mutate({ runId, stepId, resolution })
  }

  return (
    <div className="bg-orange-50 border border-orange-200 rounded-xl p-4 mb-4">
      <p className="text-sm font-semibold text-orange-900 mb-1">
        Waiting for human review
      </p>
      <p className="text-xs text-orange-700 mb-3">
        This run is paused at a human gate. Review the annotations in CVAT then approve or reject.
      </p>

      <div className="flex items-center gap-3">
        {cvatUrl && (
          <a
            href={cvatUrl}
            target="_blank"
            rel="noreferrer"
            className="text-xs border border-orange-300 text-orange-700 px-3 py-1.5 rounded-lg hover:bg-orange-100 transition-colors"
          >
            Open in CVAT →
          </a>
        )}
        <button
          onClick={() => handleResolve('approved')}
          disabled={resolve.isPending}
          className="text-xs bg-green-600 text-white px-3 py-1.5 rounded-lg hover:bg-green-700 disabled:opacity-60 transition-colors"
        >
          Approve
        </button>
        <button
          onClick={() => handleResolve('rejected')}
          disabled={resolve.isPending}
          className="text-xs bg-red-600 text-white px-3 py-1.5 rounded-lg hover:bg-red-700 disabled:opacity-60 transition-colors"
        >
          Reject
        </button>
      </div>
    </div>
  )
}
