import { useEffect } from 'react'
import { useMatch } from 'react-router-dom'
import { useUIStore } from '../store/ui'

/**
 * The project whose context the chrome (sidebar, header) should reflect.
 *
 * Project-scoped pages carry the id in the URL (`/projects/:id/*`), but several
 * detail routes break out of that prefix — `/datasets/:id`, `/runs/:id`,
 * `/models/:id`, `/workflows/:id` — so the URL alone can't tell the chrome which
 * project we're "inside". The URL wins when present (and is mirrored into the
 * store), otherwise we fall back to the last project a detail page pinned via
 * {@link usePinProject}. Returns undefined on the top-level `/projects` list so
 * the project nav collapses there.
 */
export function useActiveProjectId(): string | undefined {
  const onProjectsList = useMatch('/projects')
  const deep = useMatch('/projects/:id/*')
  const exact = useMatch('/projects/:id')
  const urlProjectId = (deep ?? exact)?.params.id
  const stored = useUIStore((s) => s.activeProjectId)
  const setActiveProject = useUIStore((s) => s.setActiveProject)

  // Keep the store in step with the URL so descending into a break-out route
  // (where urlProjectId is gone) still has a project to fall back to.
  useEffect(() => {
    if (urlProjectId) setActiveProject(urlProjectId)
  }, [urlProjectId, setActiveProject])

  if (onProjectsList) return undefined
  return urlProjectId ?? stored ?? undefined
}

/**
 * Pin the project context from a resource loaded on a break-out route, so the
 * sidebar/header keep showing the owning project's nav while it's open.
 * No-op until the id is known (resource still loading).
 */
export function usePinProject(projectId: string | undefined | null) {
  const setActiveProject = useUIStore((s) => s.setActiveProject)
  useEffect(() => {
    if (projectId) setActiveProject(projectId)
  }, [projectId, setActiveProject])
}
