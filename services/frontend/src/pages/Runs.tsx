import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useProjectRuns } from '../api/runs'
import type { RunOut } from '../api/runs'
import { Breadcrumbs, Button, EmptyState, LoadingState, StatusPill } from '../components/ui'

const FILTERS: { label: string; value?: string }[] = [
  { label: 'All' },
  { label: 'Running', value: 'running' },
  { label: 'Waiting', value: 'waiting' },
  { label: 'Failed', value: 'failed' },
  { label: 'Succeeded', value: 'succeeded' },
]

export default function Runs() {
  const { id: projectId } = useParams<{ id: string }>()
  const [status, setStatus] = useState<string | undefined>(undefined)
  const { data, isLoading, hasNextPage, isFetchingNextPage, fetchNextPage } =
    useProjectRuns(projectId, status)

  const runs: RunOut[] = data?.pages.flatMap(p => p.items) ?? []

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <Breadcrumbs
        items={[
          { label: 'Project', to: `/projects/${projectId}` },
          { label: 'Runs' },
        ]}
      />

      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold text-text-primary">Runs</h2>
        <div className="flex gap-1.5">
          {FILTERS.map(f => (
            <Button
              key={f.label}
              size="sm"
              variant={status === f.value ? 'primary' : 'secondary'}
              onClick={() => setStatus(f.value)}
            >
              {f.label}
            </Button>
          ))}
        </div>
      </div>

      {isLoading && <LoadingState />}

      {!isLoading && runs.length === 0 && (
        <EmptyState
          title="No runs yet"
          description="Runs appear here when you dispatch a workflow"
        />
      )}

      {runs.length > 0 && (
        <div className="space-y-2">
          {runs.map(run => (
            <Link
              key={run.id}
              to={`/runs/${run.id}`}
              className="flex items-center justify-between bg-surface-2 rounded-xl border border-border shadow-sm px-5 py-4 hover:border-iris/40 transition-colors"
            >
              <div className="flex items-center gap-3">
                <StatusPill status={run.status} />
                <div>
                  <p className="font-semibold text-text-primary text-sm">
                    {run.kind} · {run.id.slice(0, 8)}
                  </p>
                  <p className="text-xs text-text-muted mt-0.5">
                    {new Date(run.created_at).toLocaleString()}
                    {run.attempt > 1 && ` · attempt ${run.attempt}`}
                  </p>
                </div>
              </div>
              <span className="text-text-muted text-lg">›</span>
            </Link>
          ))}
        </div>
      )}

      {hasNextPage && (
        <Button
          variant="secondary"
          onClick={() => fetchNextPage()}
          loading={isFetchingNextPage}
          className="mt-4 w-full"
        >
          {isFetchingNextPage ? 'Loading…' : 'Load more'}
        </Button>
      )}
    </div>
  )
}
