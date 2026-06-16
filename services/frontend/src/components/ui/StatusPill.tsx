import { cn } from '../../lib/cn'

interface StatusMeta {
  label: string
  color: string
  pulse?: boolean
}

// Tolerant of the codebase's status-string drift: both `succeeded`/`completed`
// and `cancelled`/`canceled` are accepted and normalized to one display.
const STATUS: Record<string, StatusMeta> = {
  pending: { label: 'Pending', color: 'var(--text-muted)' },
  running: { label: 'Running', color: 'var(--cv-warning)', pulse: true },
  waiting: { label: 'Waiting', color: 'var(--cv-warning)' },
  succeeded: { label: 'Succeeded', color: 'var(--cv-success)' },
  completed: { label: 'Completed', color: 'var(--cv-success)' },
  failed: { label: 'Failed', color: 'var(--cv-error)' },
  cancelled: { label: 'Canceled', color: 'var(--text-muted)' },
  canceled: { label: 'Canceled', color: 'var(--text-muted)' },
}

export function StatusPill({ status, className }: { status: string; className?: string }) {
  const meta = STATUS[status.toLowerCase()] ?? { label: status, color: 'var(--text-muted)' }

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-3 px-2 py-0.5 text-xs font-medium text-text-secondary',
        className,
      )}
    >
      <span
        aria-hidden
        className={cn('h-1.5 w-1.5 flex-shrink-0 rounded-full', meta.pulse && 'animate-pulse')}
        style={{ backgroundColor: meta.color }}
      />
      {meta.label}
    </span>
  )
}
