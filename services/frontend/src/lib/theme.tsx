import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

export type ThemeMode = 'light' | 'dark' | 'system'
type ResolvedTheme = 'light' | 'dark'

interface ThemeContextValue {
  mode: ThemeMode
  resolved: ResolvedTheme
  setMode: (mode: ThemeMode) => void
  toggle: () => void
}

const STORAGE_KEY = 'cvops:theme'
const ThemeContext = createContext<ThemeContextValue | null>(null)

function readStoredMode(): ThemeMode {
  // Dark-first: default to dark when the user hasn't chosen, rather than system.
  if (typeof window === 'undefined') return 'dark'
  const v = window.localStorage.getItem(STORAGE_KEY)
  return v === 'light' || v === 'dark' || v === 'system' ? v : 'dark'
}

function systemPrefersDark(): boolean {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

function resolve(mode: ThemeMode): ResolvedTheme {
  return mode === 'system' ? (systemPrefersDark() ? 'dark' : 'light') : mode
}

function applyToDom(theme: ResolvedTheme): void {
  document.documentElement.dataset.theme = theme
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>(() => readStoredMode())
  const [resolved, setResolved] = useState<ResolvedTheme>(() => resolve(readStoredMode()))

  // Apply on mount and whenever the resolved theme changes.
  useEffect(() => {
    applyToDom(resolved)
  }, [resolved])

  // When mode flips, recompute resolved.
  useEffect(() => {
    setResolved(resolve(mode))
  }, [mode])

  // When in `system` mode, listen to OS preference changes.
  useEffect(() => {
    if (mode !== 'system') return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = (e: MediaQueryListEvent) => setResolved(e.matches ? 'dark' : 'light')
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [mode])

  const setMode = useCallback((next: ThemeMode) => {
    window.localStorage.setItem(STORAGE_KEY, next)
    setModeState(next)
  }, [])

  // Cycle: light → dark → system → light.
  const toggle = useCallback(() => {
    setMode(mode === 'light' ? 'dark' : mode === 'dark' ? 'system' : 'light')
  }, [mode, setMode])

  const value = useMemo<ThemeContextValue>(
    () => ({ mode, resolved, setMode, toggle }),
    [mode, resolved, setMode, toggle],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used inside <ThemeProvider>')
  return ctx
}

/**
 * Inline script source string for the document <head>. Sets data-theme
 * before React mounts so dark-mode users don't flash a light page.
 * Add to index.html as:  <script>{themeBootScript}</script>
 */
export const themeBootScript = `(function () {
  try {
    var stored = localStorage.getItem('${STORAGE_KEY}');
    var mode = stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'dark';
    var resolved = mode === 'system'
      ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
      : mode;
    document.documentElement.dataset.theme = resolved;
  } catch (_) {}
})();`
