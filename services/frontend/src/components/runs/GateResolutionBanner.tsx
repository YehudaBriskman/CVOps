import { useResolveGate } from '../../api/runs'
import { Button } from '../ui'

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
    <div className="mb-4 rounded-xl border border-warning/40 bg-warning/5 p-4">
      <div className="mb-1 flex items-center gap-2">
        <span aria-hidden className="h-2 w-2 animate-pulse rounded-full bg-warning" />
        <p className="text-sm font-semibold text-text-primary">Waiting for human review</p>
      </div>
      <p className="mb-3 text-xs text-text-secondary">
        This run is paused at a human gate. Review the annotations in CVAT, then approve or reject.
      </p>

      <div className="flex items-center gap-2">
        {cvatUrl && (
          <a href={cvatUrl} target="_blank" rel="noreferrer">
            <Button variant="secondary" size="sm">Open in CVAT →</Button>
          </a>
        )}
        <Button
          size="sm"
          className="bg-success hover:opacity-90"
          loading={resolve.isPending}
          onClick={() => handleResolve('approved')}
        >
          Approve
        </Button>
        <Button
          variant="danger"
          size="sm"
          loading={resolve.isPending}
          onClick={() => handleResolve('rejected')}
        >
          Reject
        </Button>
      </div>
    </div>
  )
}
