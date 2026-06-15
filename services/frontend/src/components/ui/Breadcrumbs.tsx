import { Fragment } from 'react'
import { Link } from 'react-router-dom'
import { cn } from '../../lib/cn'

export interface Crumb {
  label: string
  to?: string
  /** Render the label in monospace (used for hashes/ids). */
  mono?: boolean
}

export function Breadcrumbs({ items, className }: { items: Crumb[]; className?: string }) {
  return (
    <nav aria-label="Breadcrumb" className={cn('mb-6 flex items-center gap-2 text-sm text-text-muted', className)}>
      {items.map((c, i) => (
        <Fragment key={i}>
          {i > 0 && <span aria-hidden>/</span>}
          {c.to ? (
            <Link to={c.to} className="hover:text-iris">
              {c.label}
            </Link>
          ) : (
            <span className={cn('text-text-secondary', c.mono ? 'font-mono' : 'font-medium')}>{c.label}</span>
          )}
        </Fragment>
      ))}
    </nav>
  )
}
