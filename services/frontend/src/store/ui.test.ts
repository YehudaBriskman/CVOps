import { beforeEach, describe, expect, it } from 'vitest'
import { useUIStore } from './ui'

const initial = useUIStore.getState()

describe('useUIStore', () => {
  beforeEach(() => {
    useUIStore.setState({ sidebarOpen: initial.sidebarOpen, commandOpen: initial.commandOpen })
  })

  it('starts with the sidebar open and command palette closed', () => {
    expect(useUIStore.getState().sidebarOpen).toBe(true)
    expect(useUIStore.getState().commandOpen).toBe(false)
  })

  it('toggleSidebar flips the sidebar state', () => {
    useUIStore.getState().toggleSidebar()
    expect(useUIStore.getState().sidebarOpen).toBe(false)
    useUIStore.getState().toggleSidebar()
    expect(useUIStore.getState().sidebarOpen).toBe(true)
  })

  it('setCommandOpen sets the palette state explicitly', () => {
    useUIStore.getState().setCommandOpen(true)
    expect(useUIStore.getState().commandOpen).toBe(true)
    useUIStore.getState().setCommandOpen(false)
    expect(useUIStore.getState().commandOpen).toBe(false)
  })
})
