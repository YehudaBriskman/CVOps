import { useLocation } from 'react-router-dom'

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

export function Header() {
  const location = useLocation()
  const title = getTitle(location.pathname)

  return (
    <header className="h-14 border-b border-cloud bg-white flex items-center px-6 flex-shrink-0 gap-3">
      <h1 className="text-ink font-semibold text-base flex-1 truncate">{title}</h1>
      <div className="w-8 h-8 rounded-full bg-cobalt flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
        U
      </div>
    </header>
  )
}
