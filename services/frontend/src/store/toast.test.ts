import { beforeEach, describe, expect, it } from 'vitest'
import { toast, useToastStore } from './toast'

describe('toast store', () => {
  beforeEach(() => {
    useToastStore.setState({ toasts: [] })
  })

  it('push adds a toast with a generated id and returns it', () => {
    const id = useToastStore.getState().push({ title: 'Hi', variant: 'info', duration: 1000 })
    const toasts = useToastStore.getState().toasts
    expect(toasts).toHaveLength(1)
    expect(toasts[0].id).toBe(id)
    expect(toasts[0].title).toBe('Hi')
  })

  it('generates unique ids across pushes', () => {
    const a = useToastStore.getState().push({ title: 'A', variant: 'info', duration: 0 })
    const b = useToastStore.getState().push({ title: 'B', variant: 'info', duration: 0 })
    expect(a).not.toBe(b)
    expect(useToastStore.getState().toasts).toHaveLength(2)
  })

  it('dismiss removes only the matching toast', () => {
    const a = useToastStore.getState().push({ title: 'A', variant: 'info', duration: 0 })
    useToastStore.getState().push({ title: 'B', variant: 'info', duration: 0 })
    useToastStore.getState().dismiss(a)
    const toasts = useToastStore.getState().toasts
    expect(toasts).toHaveLength(1)
    expect(toasts[0].title).toBe('B')
  })

  it('toast.error uses the longer 6500ms default duration', () => {
    toast.error('Boom')
    expect(useToastStore.getState().toasts[0].duration).toBe(6500)
  })

  it('toast.success uses the 4000ms default duration', () => {
    toast.success('Saved')
    expect(useToastStore.getState().toasts[0].duration).toBe(4000)
  })

  it('an explicit duration overrides the variant default', () => {
    toast.error('Boom', undefined, 100)
    expect(useToastStore.getState().toasts[0].duration).toBe(100)
  })

  it('helpers set the right variant', () => {
    toast.warning('careful', 'details')
    const t = useToastStore.getState().toasts[0]
    expect(t.variant).toBe('warning')
    expect(t.description).toBe('details')
  })
})
