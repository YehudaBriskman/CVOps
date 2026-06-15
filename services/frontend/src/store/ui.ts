import { create } from 'zustand'

interface UIState {
  sidebarOpen: boolean
  toggleSidebar: () => void
  commandOpen: boolean
  setCommandOpen: (open: boolean) => void
  /** Project whose nav the chrome shows on break-out routes (/runs/:id, etc.)
   *  where the URL carries no project id. See lib/useActiveProject. */
  activeProjectId: string | null
  setActiveProject: (id: string | null) => void
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  commandOpen: false,
  setCommandOpen: (open) => set({ commandOpen: open }),
  activeProjectId: null,
  setActiveProject: (id) => set({ activeProjectId: id }),
}))
