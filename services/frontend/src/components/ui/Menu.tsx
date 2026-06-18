import { useEffect, useRef, useState, type ReactNode } from 'react'

interface MenuProps {
  /** Content rendered inside the trigger button (e.g. an avatar initial). */
  triggerContent: ReactNode
  /** Accessible label for both the trigger and the menu. */
  triggerLabel: string
  /** Class names applied to the trigger button. */
  triggerClassName?: string
  /** Which edge of the trigger the panel aligns to. */
  align?: 'left' | 'right'
  children: ReactNode
}

/**
 * Small, dependency-free dropdown menu. The trigger toggles a floating panel
 * that closes on outside-click and Escape (returning focus to the trigger),
 * and moves focus to the first item on open. Semantic tokens only.
 */
export function Menu({
  triggerContent,
  triggerLabel,
  triggerClassName,
  align = 'right',
  children,
}: MenuProps) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onPointerDown(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        setOpen(false)
        triggerRef.current?.focus()
      }
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    // Pull focus into the menu so keyboard users land on the first item.
    panelRef.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus()
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  return (
    <div ref={rootRef} className="relative flex-shrink-0">
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={triggerLabel}
        onClick={() => setOpen((v) => !v)}
        className={triggerClassName}
      >
        {triggerContent}
      </button>
      {open && (
        <div
          ref={panelRef}
          role="menu"
          aria-label={triggerLabel}
          className={`absolute z-50 mt-2 w-56 overflow-hidden rounded-lg border border-border bg-surface-2 py-1 shadow-lg ${
            align === 'right' ? 'right-0' : 'left-0'
          }`}
        >
          {children}
        </div>
      )}
    </div>
  )
}

interface MenuItemProps {
  onClick?: () => void
  children: ReactNode
}

export function MenuItem({ onClick, children }: MenuItemProps) {
  return (
    <button
      type="button"
      role="menuitem"
      onClick={onClick}
      className="flex w-full items-center px-3 py-2 text-left text-sm text-text-secondary transition-colors hover:bg-surface-1 hover:text-text-primary focus:bg-surface-1 focus:text-text-primary focus:outline-none"
    >
      {children}
    </button>
  )
}
