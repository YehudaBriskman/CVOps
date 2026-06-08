import { NavLink, Link, useMatch } from 'react-router-dom'
import clsx from 'clsx'
import { MOCK_PROJECTS } from '../../mock/data'

function navClass({ isActive }: { isActive: boolean }) {
  return clsx(
    'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
    isActive
      ? 'bg-slate-700 text-white'
      : 'text-slate-400 hover:bg-slate-800 hover:text-white',
  )
}

function ProjectNav({ projectId }: { projectId: string }) {
  const project = MOCK_PROJECTS.find(p => p.id === projectId)

  const items = [
    { to: `/projects/${projectId}`,              label: 'Dashboard',    end: true  },
    { to: `/projects/${projectId}/data-sources`, label: 'Data Sources', end: false },
    { to: `/projects/${projectId}/samples`,      label: 'Samples',      end: false },
    { to: `/projects/${projectId}/datasets`,     label: 'Datasets',     end: false },
    { to: `/projects/${projectId}/workflows`,    label: 'Workflows',    end: false },
    { to: `/projects/${projectId}/models`,       label: 'Models',       end: false },
    { to: `/projects/${projectId}/settings`,     label: 'Settings',     end: false },
  ]

  return (
    <div className="mt-5">
      <p className="px-3 mb-1.5 text-[10px] font-bold text-slate-500 uppercase tracking-widest truncate">
        {project?.name ?? 'Project'}
      </p>
      <nav className="space-y-0.5">
        {items.map(item => (
          <NavLink key={item.to} to={item.to} end={item.end} className={navClass}>
            {item.label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}

export function Sidebar() {
  const matchDeep  = useMatch('/projects/:id/*')
  const matchExact = useMatch('/projects/:id')
  const projectId  = (matchDeep ?? matchExact)?.params.id

  return (
    <aside className="w-60 bg-slate-900 flex flex-col flex-shrink-0 overflow-hidden">
      {/* Logo */}
      <div className="h-14 flex items-center px-4 border-b border-slate-800 flex-shrink-0">
        <Link to="/projects" className="flex items-center gap-2 text-white font-bold text-lg">
          <span className="text-indigo-400 text-xl">◈</span>
          CVOps
        </Link>
      </div>

      {/* Nav */}
      <div className="flex-1 overflow-y-auto p-3">
        <nav className="space-y-0.5">
          <NavLink to="/projects" end className={navClass}>
            All Projects
          </NavLink>
        </nav>

        {projectId && <ProjectNav projectId={projectId} />}
      </div>

      {/* User */}
      <div className="p-3 border-t border-slate-800 flex-shrink-0">
        <div className="flex items-center gap-2.5 px-3 py-2">
          <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
            U
          </div>
          <span className="text-slate-400 text-sm truncate">user@cvops.io</span>
        </div>
      </div>
    </aside>
  )
}
