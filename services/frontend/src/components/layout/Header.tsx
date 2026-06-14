import { useLocation } from 'react-router-dom'
import { useTheme, type ThemeMode } from '../../lib/theme'

function getTitle(pathname: string): string {
  if (pathname.endsWith('/data-sources')) return 'Data Sources'
  if (pathname.endsWith('/samples'))      return 'Samples'
  if (pathname.endsWith('/datasets'))     return 'Datasets'
  if (pathname.endsWith('/workflows'))    return 'Workflows'
  if (pathname.endsWith('/models'))       return 'Models'
  if (pathname.endsWith('/settings'))     return 'Settings'
  if (pathname.startsWith('/workflows/')) return 'Workflow Builder'
  if (pathname.startsWith('/runs/'))      return 'Run View'
  if (pathname.startsWith('/projects/'))  return 'Project'
  if (pathname === '/projects')           return 'Projects'
  return 'CVOps'
}

const themeLabel: Record<ThemeMode, string> = {
  light:  'Switch to dark theme',
  dark:   'Switch to system theme',
  system: 'Switch to light theme',
}

export function Header() {
  const location = useLocation()
  const { mode, toggle } = useTheme()
  const title = getTitle(location.pathname)

  return (
    <header className="h-14 border-b border-border bg-surface-2 flex items-center px-6 flex-shrink-0 gap-3">
      <h1 className="text-text-primary font-semibold text-base flex-1 truncate">{title}</h1>

      <button
        type="button"
        onClick={toggle}
        aria-label={themeLabel[mode]}
        title={themeLabel[mode]}
        className="h-8 w-8 rounded-lg text-text-secondary hover:bg-surface-1 hover:text-text-primary transition-colors flex items-center justify-center flex-shrink-0"
      >
        <ThemeIcon mode={mode} />
      </button>

      <div className="w-8 h-8 rounded-full bg-cobalt flex items-center justify-center text-text-onAccent text-sm font-bold flex-shrink-0">
        U
      </div>
    </header>
  )
}

function ThemeIcon({ mode }: { mode: ThemeMode }) {
  // Lucide-styled SVGs (1.5px stroke). We'll switch to lucide-react in step 2.
  if (mode === 'dark') {
    // moon
    return (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
           stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"
           aria-hidden="true">
        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79Z"/>
      </svg>
    )
  }
  if (mode === 'light') {
    // sun
    return (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
           stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"
           aria-hidden="true">
        <circle cx="12" cy="12" r="4"/>
        <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/>
      </svg>
    )
  }
  // monitor (system)
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"
         aria-hidden="true">
      <rect x="2" y="3" width="20" height="14" rx="2"/>
      <path d="M8 21h8M12 17v4"/>
    </svg>
  )
}
