import { NavLink, Link, useMatch } from 'react-router-dom'
import clsx from 'clsx'

function navClass({ isActive }: { isActive: boolean }) {
  return clsx(
    'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
    isActive
      ? 'bg-surface-3 text-text-primary'
      : 'text-text-muted hover:bg-surface-3 hover:text-text-primary',
  )
}

function ProjectNav({ projectId }: { projectId: string }) {
  const items = [
    { to: `/projects/${projectId}`,              label: 'Dashboard',    end: true  },
    { to: `/projects/${projectId}/data-sources`, label: 'Data Sources', end: false },
    { to: `/projects/${projectId}/samples`,      label: 'Samples',      end: false },
    { to: `/projects/${projectId}/datasets`,     label: 'Datasets',     end: false },
    { to: `/projects/${projectId}/workflows`,    label: 'Workflows',    end: false },
    { to: `/projects/${projectId}/runs`,         label: 'Runs',         end: false },
    { to: `/projects/${projectId}/models`,       label: 'Models',       end: false },
    { to: `/projects/${projectId}/settings`,     label: 'Settings',     end: false },
  ]

  return (
    <div className="mt-5">
      <p className="px-3 mb-1.5 text-[10px] font-bold text-text-secondary uppercase tracking-widest truncate">
        Project
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
    <aside className="w-60 bg-surface-2 flex flex-col flex-shrink-0 overflow-hidden">
      {/* Logo */}
      <div className="h-14 flex items-center px-4 border-b border-border flex-shrink-0">
        <Link to="/projects" className="flex items-center gap-2 text-text-primary font-bold text-lg">
          <span className="text-iris-400 text-xl">◈</span>
          CVOps
        </Link>
      </div>

      {/* Nav */}
      <div className="flex-1 overflow-y-auto p-3">
        <nav className="space-y-0.5">
          <NavLink to="/projects" end className={navClass}>
            All Projects
          </NavLink>
          <NavLink to="/cvat-models" className={navClass}>
            Models
          </NavLink>
        </nav>

        {projectId && <ProjectNav projectId={projectId} />}
      </div>
    </aside>
  )
}
