import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { API } from '../../test/handlers'
import { server } from '../../test/server'
import { renderWithProviders } from '../../test/utils'
import { TagPicker } from './TagPicker'

function tagsHandler(tags: Array<{ id: string; name: string }>) {
  return http.get(`${API}/projects/p1/tags`, () =>
    HttpResponse.json(
      tags.map((t) => ({ ...t, project_id: 'p1', color: '#888', created_at: '2026-01-01' })),
    ),
  )
}

describe('TagPicker', () => {
  it('renders existing tags as chips', async () => {
    server.use(tagsHandler([{ id: 't1', name: 'car' }, { id: 't2', name: 'bus' }]))
    renderWithProviders(<TagPicker projectId="p1" value={[]} onChange={() => {}} />)
    expect(await screen.findByText('car')).toBeInTheDocument()
    expect(screen.getByText('bus')).toBeInTheDocument()
  })

  it('toggles a tag id on click (add then remove)', async () => {
    server.use(tagsHandler([{ id: 't1', name: 'car' }]))
    const onChange = vi.fn()
    const { rerender } = renderWithProviders(
      <TagPicker projectId="p1" value={[]} onChange={onChange} />,
    )
    const chip = await screen.findByText('car')
    await userEvent.click(chip)
    expect(onChange).toHaveBeenCalledWith(['t1'])

    // simulate the parent applying the new value, then clicking again removes it
    rerender(<TagPicker projectId="p1" value={['t1']} onChange={onChange} />)
    await userEvent.click(screen.getByText('car'))
    expect(onChange).toHaveBeenLastCalledWith([])
  })

  it('shows an empty hint when there are no tags', async () => {
    server.use(tagsHandler([]))
    renderWithProviders(<TagPicker projectId="p1" value={[]} onChange={() => {}} />)
    expect(await screen.findByText(/No tags yet/i)).toBeInTheDocument()
  })

  it('creates a tag on Enter and selects it', async () => {
    server.use(
      tagsHandler([]),
      http.post(`${API}/projects/p1/tags`, async ({ request }) => {
        const body = (await request.json()) as { name: string }
        return HttpResponse.json({
          id: 't9',
          project_id: 'p1',
          name: body.name,
          color: '#888',
          created_at: '2026-01-01',
        })
      }),
    )
    const onChange = vi.fn()
    renderWithProviders(<TagPicker projectId="p1" value={[]} onChange={onChange} />)
    const input = await screen.findByPlaceholderText(/New tag name/i)
    await userEvent.type(input, 'truck{Enter}')
    await waitFor(() => expect(onChange).toHaveBeenCalledWith(['t9']))
  })
})
