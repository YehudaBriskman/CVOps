import { type ReactNode } from 'react'
import { cn } from '../../lib/cn'

type Tone = 'neutral' | 'info' | 'success' | 'warning' | 'error'

const TONES: Record<Tone, string> = {
  neutral: 'bg-surface-3 text-text-secondary border-border',
  info: 'bg-cobalt/10 text-cobalt-400 border-cobalt/30',
  success: 'bg-success/10 text-success border-success/30',
  warning: 'bg-warning/10 text-warning border-warning/30',
  error: 'bg-error/10 text-error border-error/30',
}

export function Badge({
  tone = 'neutral',
  className,
  children,
}: {
  tone?: Tone
  className?: string
  children: ReactNode
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium',
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}
