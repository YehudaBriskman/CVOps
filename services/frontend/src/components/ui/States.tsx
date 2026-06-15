import { type ReactNode } from 'react'
import { cn } from '../../lib/cn'
import { Button } from './Button'

/** Designed empty state — teaches the next action rather than showing a blank panel. */
export function EmptyState({
  title,
  description,
  action,
  icon,
  className,
}: {
  title: string
  description?: string
  action?: ReactNode
  icon?: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        'rounded-xl border border-border bg-surface-2 p-10 text-center shadow-sm',
        className,
      )}
    >
      {icon && <div className="mb-3 flex justify-center text-text-muted">{icon}</div>}
      <p className="text-sm font-medium text-text-primary">{title}</p>
      {description && <p className="mx-auto mt-1 max-w-sm text-xs text-text-muted">{description}</p>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  )
}

/** Error state with cause + retry — pairs with a TanStack Query `refetch`. */
export function ErrorState({
  title = 'Something went wrong',
  description,
  onRetry,
  className,
}: {
  title?: string
  description?: string
  onRetry?: () => void
  className?: string
}) {
  return (
    <div
      role="alert"
      className={cn(
        'rounded-xl border border-error/30 bg-error/5 p-8 text-center',
        className,
      )}
    >
      <p className="text-sm font-medium text-error">{title}</p>
      {description && <p className="mx-auto mt-1 max-w-sm text-xs text-text-muted">{description}</p>}
      {onRetry && (
        <div className="mt-4 flex justify-center">
          <Button variant="secondary" size="sm" onClick={onRetry}>
            Try again
          </Button>
        </div>
      )}
    </div>
  )
}
