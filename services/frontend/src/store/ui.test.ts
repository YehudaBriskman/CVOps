import { beforeEach, describe, expect, it } from 'vitest'
import { useUIStore } from './ui'

describe('useUIStore', () => {
  beforeEach(() => useUIStore.setState({ sidebarOpen: true, commandOpen: false }))

  it('toggleSidebar flips sidebarOpen', () => {
    expect(useUIStore.getState().sidebarOpen).toBe(true)
    useUIStore.getState().toggleSidebar()
    expect(useUIStore.getState().sidebarOpen).toBe(false)
    useUIStore.getState().toggleSidebar()
    expect(useUIStore.getState().sidebarOpen).toBe(true)
  })

  it('setCommandOpen sets commandOpen', () => {
    expect(useUIStore.getState().commandOpen).toBe(false)
    useUIStore.getState().setCommandOpen(true)
    expect(useUIStore.getState().commandOpen).toBe(true)
    useUIStore.getState().setCommandOpen(false)
    expect(useUIStore.getState().commandOpen).toBe(false)
  })
})
