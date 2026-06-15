import { create } from 'zustand'

export type ToastVariant = 'info' | 'success' | 'error' | 'warning'

export interface Toast {
  id: string
  title: string
  description?: string
  variant: ToastVariant
  /** ms before auto-dismiss; 0 keeps it until manually closed */
  duration: number
}

interface ToastState {
  toasts: Toast[]
  push: (t: Omit<Toast, 'id'>) => string
  dismiss: (id: string) => void
}

let counter = 0

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  push: (t) => {
    const id = `toast-${++counter}`
    set((s) => ({ toasts: [...s.toasts, { ...t, id }] }))
    return id
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((x) => x.id !== id) })),
}))

function emit(variant: ToastVariant, title: string, description?: string, duration?: number): string {
  // Errors linger longer; everything else auto-dismisses on the design-plan 4s.
  const fallback = variant === 'error' ? 6500 : 4000
  return useToastStore.getState().push({
    variant,
    title,
    description,
    duration: duration ?? fallback,
  })
}

/**
 * Imperative toast API usable outside of React (e.g. the TanStack Query global
 * error handlers in queryClient.ts), as well as inside components.
 */
export const toast = {
  info: (title: string, description?: string, duration?: number) => emit('info', title, description, duration),
  success: (title: string, description?: string, duration?: number) => emit('success', title, description, duration),
  warning: (title: string, description?: string, duration?: number) => emit('warning', title, description, duration),
  error: (title: string, description?: string, duration?: number) => emit('error', title, description, duration),
  dismiss: (id: string) => useToastStore.getState().dismiss(id),
}
