interface Props {
  stats: Record<string, unknown> | null | undefined
}

const SPLIT_COLOR: Record<string, string> = {
  train: 'bg-iris',
  val:   'bg-warning',
  test:  'bg-success',
}

export function CommitStats({ stats }: Props) {
  if (!stats || Object.keys(stats).length === 0) return null

  const sampleCount = stats.sample_count as number | undefined
  const byClass = stats.by_class as Record<string, number> | undefined
  const bySplit = stats.by_split as Record<string, number> | undefined

  return (
    <div className="space-y-4">
      {bySplit && Object.keys(bySplit).length > 0 && (
        <div className="bg-surface-2 rounded-xl border border-border shadow-sm p-5">
          <p className="text-xs font-bold text-text-muted uppercase tracking-wider mb-3">Split</p>
          <div className="space-y-2">
            {Object.entries(bySplit).map(([split, count]) => {
              const pct = sampleCount ? Math.round((count / sampleCount) * 100) : 0
              return (
                <div key={split}>
                  <div className="flex justify-between text-xs text-text-secondary mb-1">
                    <span className="capitalize">{split}</span>
                    <span>{count} ({pct}%)</span>
                  </div>
                  <div className="h-2 bg-surface-3 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${SPLIT_COLOR[split] ?? 'bg-text-muted'}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {byClass && Object.keys(byClass).length > 0 && (
        <div className="bg-surface-2 rounded-xl border border-border shadow-sm p-5">
          <p className="text-xs font-bold text-text-muted uppercase tracking-wider mb-3">Classes</p>
          <div className="space-y-2">
            {Object.entries(byClass)
              .sort(([, a], [, b]) => b - a)
              .map(([cls, count]) => {
                const max = Math.max(...Object.values(byClass))
                const pct = Math.round((count / max) * 100)
                return (
                  <div key={cls}>
                    <div className="flex justify-between text-xs text-text-secondary mb-1">
                      <span>{cls}</span>
                      <span>{count}</span>
                    </div>
                    <div className="h-2 bg-surface-3 rounded-full overflow-hidden">
                      <div className="h-full bg-iris rounded-full" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                )
              })}
          </div>
        </div>
      )}

      {sampleCount != null && !bySplit && !byClass && (
        <div className="bg-surface-2 rounded-xl border border-border shadow-sm p-5">
          <p className="text-3xl font-bold text-text-primary">{sampleCount}</p>
          <p className="text-xs text-text-muted mt-1">samples</p>
        </div>
      )}
    </div>
  )
}
