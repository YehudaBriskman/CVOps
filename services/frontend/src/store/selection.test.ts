import { beforeEach, describe, expect, it } from 'vitest'
import { useSelectionStore } from './selection'

describe('useSelectionStore', () => {
  beforeEach(() => useSelectionStore.getState().clear())

  it('toggles an id on and off', () => {
    const { toggle } = useSelectionStore.getState()
    toggle('a')
    expect(useSelectionStore.getState().selected.has('a')).toBe(true)
    toggle('a')
    expect(useSelectionStore.getState().selected.has('a')).toBe(false)
  })

  it('adds many ids without duplicating', () => {
    const { add } = useSelectionStore.getState()
    add(['a', 'b', 'b', 'c'])
    expect(useSelectionStore.getState().selected).toEqual(new Set(['a', 'b', 'c']))
  })

  it('clear empties the selection', () => {
    useSelectionStore.getState().add(['a', 'b'])
    useSelectionStore.getState().clear()
    expect(useSelectionStore.getState().selected.size).toBe(0)
  })
})
