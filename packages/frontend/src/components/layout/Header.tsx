import { useLocation, useMatch } from 'react-router-dom'
import { MOCK_PROJECTS } from '../../mock/data'

function getTitle(pathname: string, projectName?: string): string {
  if (pathname.endsWith('/data-sources')) return 'Data Sources'
  if (pathname.endsWith('/samples'))      return 'Samples'
  if (pathname.endsWith('/datasets'))     return 'Datasets'
  if (pathname.endsWith('/workflows'))    return 'Workflows'
  if (pathname.endsWith('/models'))       return 'Models'
  if (pathname.endsWith('/settings'))     return 'Settings'
  if (pathname.startsWith('/workflows/')) return 'Workflow Builder'
  if (pathname.startsWith('/runs/'))      return 'Run View'
  if (pathname.startsWith('/projects/') && projectName) return projectName
  if (pathname === '/projects')           return 'Projects'
  return 'CVOps'
}

export function Header() {
  const location = useLocation()
  const matchDeep  = useMatch('/projects/:id/*')
  const matchExact = useMatch('/projects/:id')
  const projectId  = (matchDeep ?? matchExact)?.params.id
  const project    = MOCK_PROJECTS.find(p => p.id === projectId)
  const title      = getTitle(location.pathname, project?.name)

  return (
    <header className="h-14 border-b border-slate-200 bg-white flex items-center px-6 flex-shrink-0 gap-3">
      <h1 className="text-slate-800 font-semibold text-base flex-1 truncate">{title}</h1>
      <div className="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
        U
      </div>
    </header>
  )
}
