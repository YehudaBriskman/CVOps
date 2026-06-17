import type { Commit } from '../../api/datasets'
import { cn } from '../../lib/cn'

interface Props {
  commits: Commit[]
  selectedId: string | null
  onSelect: (id: string) => void
}

/**
 * Vertical commit timeline rail. Each commit is a node on a single trunk line;
 * selecting one drives the contents pane beside it. The commits endpoint returns
 * a linear history newest-first, so the rail reads top (newest) → bottom (oldest)
 * and renders a trunk rather than a branching DAG. The trunk connector is drawn
 * below every node except the last, joining adjacent nodes top-to-bottom.
 */
export function CommitGraph({ commits, selectedId, onSelect }: Props) {
  if (commits.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-surface-2 p-6 text-center shadow-sm">
        <p className="text-sm font-medium text-text-primary">No commits yet</p>
        <p className="mt-1 text-xs text-text-muted">Commits are created by workflow commit steps</p>
      </div>
    )
  }

  return (
    <ol className="space-y-1">
      {commits.map((c, i) => {
        const selected = c.id === selectedId
        const count = (c.stats?.sample_count as number | undefined) ?? null
        return (
          <li key={c.id}>
            <button
              type="button"
              onClick={() => onSelect(c.id)}
              aria-current={selected}
              className={cn(
                'flex w-full items-stretch gap-3 rounded-lg border px-3 py-2 text-left transition-colors',
                selected
                  ? 'border-iris bg-iris/10'
                  : 'border-transparent hover:border-border hover:bg-surface-2',
              )}
            >
              <div className="flex flex-col items-center">
                <span
                  className={cn(
                    'mt-1 h-3 w-3 shrink-0 rounded-full border-2 border-surface-1',
                    selected ? 'bg-iris ring-2 ring-iris/40' : 'bg-text-muted',
                  )}
                />
                {i < commits.length - 1 && <span className="mt-0.5 w-0.5 flex-1 bg-border" />}
              </div>
              <div className="min-w-0 flex-1 pb-1">
                <p className={cn('truncate text-sm', selected ? 'font-semibold text-text-primary' : 'font-medium text-text-secondary')}>
                  {c.message ?? 'Commit'}
                </p>
                <p className="mt-0.5 flex items-center gap-2 text-xs text-text-muted">
                  <span className="font-mono">{c.id.slice(0, 7)}</span>
                  <span>·</span>
                  <span>{new Date(c.created_at).toLocaleDateString()}</span>
                  {count != null && (
                    <>
                      <span>·</span>
                      <span>{count} samples</span>
                    </>
                  )}
                </p>
              </div>
            </button>
          </li>
        )
      })}
    </ol>
  )
}
