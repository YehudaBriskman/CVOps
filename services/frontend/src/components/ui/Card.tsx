import { type HTMLAttributes } from 'react'
import { cn } from '../../lib/cn'

export function Card({ className, children, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('rounded-xl border border-border bg-surface-2 shadow-sm', className)}
      {...rest}
    >
      {children}
    </div>
  )
}
