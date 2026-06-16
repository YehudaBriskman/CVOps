import { useEffect } from 'react'
import { useToastStore, type Toast, type ToastVariant } from '../../store/toast'

const ACCENT: Record<ToastVariant, string> = {
  info: 'var(--cv-info)',
  success: 'var(--cv-success)',
  warning: 'var(--cv-warning)',
  error: 'var(--cv-error)',
}

const GLYPH: Record<ToastVariant, string> = {
  info: 'ℹ',
  success: '✓',
  warning: '!',
  error: '✕',
}

function ToastItem({ toast }: { toast: Toast }) {
  const dismiss = useToastStore((s) => s.dismiss)

  useEffect(() => {
    if (toast.duration <= 0) return
    const t = setTimeout(() => dismiss(toast.id), toast.duration)
    return () => clearTimeout(t)
  }, [toast.id, toast.duration, dismiss])

  return (
    <div
      className="pointer-events-auto flex w-80 items-start gap-3 rounded-lg border border-strong bg-surface-2 p-3 shadow-lg"
      style={{ borderLeftColor: ACCENT[toast.variant], borderLeftWidth: 3 }}
    >
      <span
        aria-hidden
        className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold text-text-onAccent"
        style={{ backgroundColor: ACCENT[toast.variant] }}
      >
        {GLYPH[toast.variant]}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-text-primary">{toast.title}</p>
        {toast.description && (
          <p className="mt-0.5 break-words text-xs text-text-muted">{toast.description}</p>
        )}
      </div>
      <button
        type="button"
        aria-label="Dismiss notification"
        onClick={() => dismiss(toast.id)}
        className="flex-shrink-0 rounded p-0.5 text-text-muted transition-colors hover:text-text-primary"
      >
        ✕
      </button>
    </div>
  )
}

export function Toaster() {
  const toasts = useToastStore((s) => s.toasts)

  return (
    <div
      aria-live="polite"
      aria-atomic="false"
      className="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2"
    >
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} />
      ))}
    </div>
  )
}
