import { useEffect, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '../../lib/cn'

/** Right-side slide-in panel. Used for the workflow step config panel and detail views. */
export function Drawer({
  open,
  onClose,
  title,
  children,
  width = 'w-[420px]',
}: {
  open: boolean
  onClose: () => void
  title?: string
  children: ReactNode
  width?: string
}) {
  useEffect(() => {
    if (!open) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  return createPortal(
    <div className={cn('fixed inset-0 z-40', !open && 'pointer-events-none')}>
      <div
        aria-hidden
        onClick={onClose}
        className={cn(
          'absolute inset-0 bg-black/40 transition-opacity duration-200',
          open ? 'opacity-100' : 'opacity-0',
        )}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cn(
          'absolute right-0 top-0 flex h-full max-w-[90vw] flex-col border-l border-border bg-surface-2 shadow-lg transition-transform duration-200',
          width,
          open ? 'translate-x-0' : 'translate-x-full',
        )}
      >
        {title && (
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold text-text-primary">{title}</h2>
            <button
              type="button"
              aria-label="Close panel"
              onClick={onClose}
              className="rounded p-1 text-text-muted transition-colors hover:bg-surface-3 hover:text-text-primary"
            >
              ✕
            </button>
          </div>
        )}
        <div className="flex-1 overflow-auto p-4">{children}</div>
      </aside>
    </div>,
    document.body,
  )
}
