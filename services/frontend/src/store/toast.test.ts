import { beforeEach, describe, expect, it } from 'vitest'
import { toast, useToastStore } from './toast'

describe('useToastStore', () => {
  beforeEach(() => useToastStore.setState({ toasts: [] }))

  it('push returns an id and appends the toast', () => {
    const id = useToastStore.getState().push({ title: 'Hi', variant: 'info', duration: 1000 })
    expect(id).toMatch(/^toast-\d+$/)
    const toasts = useToastStore.getState().toasts
    expect(toasts).toHaveLength(1)
    expect(toasts[0]).toMatchObject({ id, title: 'Hi', variant: 'info', duration: 1000 })
  })

  it('push appends in order, each with a distinct id', () => {
    const id1 = useToastStore.getState().push({ title: 'A', variant: 'info', duration: 1000 })
    const id2 = useToastStore.getState().push({ title: 'B', variant: 'success', duration: 1000 })
    expect(id1).not.toBe(id2)
    const toasts = useToastStore.getState().toasts
    expect(toasts.map((t) => t.title)).toEqual(['A', 'B'])
  })

  it('dismiss removes the toast by id', () => {
    const id1 = useToastStore.getState().push({ title: 'A', variant: 'info', duration: 1000 })
    const id2 = useToastStore.getState().push({ title: 'B', variant: 'info', duration: 1000 })
    useToastStore.getState().dismiss(id1)
    const toasts = useToastStore.getState().toasts
    expect(toasts).toHaveLength(1)
    expect(toasts[0].id).toBe(id2)
  })
})

describe('toast imperative helpers', () => {
  beforeEach(() => useToastStore.setState({ toasts: [] }))

  it('info pushes with variant info and default duration 4000', () => {
    toast.info('Title', 'Desc')
    const t = useToastStore.getState().toasts[0]
    expect(t).toMatchObject({ variant: 'info', title: 'Title', description: 'Desc', duration: 4000 })
  })

  it('success pushes with variant success and default duration 4000', () => {
    toast.success('Title')
    const t = useToastStore.getState().toasts[0]
    expect(t).toMatchObject({ variant: 'success', title: 'Title', duration: 4000 })
  })

  it('warning pushes with variant warning and default duration 4000', () => {
    toast.warning('Title')
    const t = useToastStore.getState().toasts[0]
    expect(t).toMatchObject({ variant: 'warning', title: 'Title', duration: 4000 })
  })

  it('error pushes with variant error and default duration 6500', () => {
    toast.error('Boom')
    const t = useToastStore.getState().toasts[0]
    expect(t).toMatchObject({ variant: 'error', title: 'Boom', duration: 6500 })
  })

  it('respects an explicit duration over the variant default', () => {
    toast.error('Boom', undefined, 999)
    const t = useToastStore.getState().toasts[0]
    expect(t.duration).toBe(999)
  })

  it('returns the pushed toast id, dismissable via toast.dismiss', () => {
    const id = toast.info('Title')
    expect(useToastStore.getState().toasts).toHaveLength(1)
    toast.dismiss(id)
    expect(useToastStore.getState().toasts).toHaveLength(0)
  })
})
