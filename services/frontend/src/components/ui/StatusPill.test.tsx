import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { StatusPill } from './StatusPill'

describe('StatusPill', () => {
  it('renders the friendly label for a known status', () => {
    render(<StatusPill status="running" />)
    expect(screen.getByText('Running')).toBeInTheDocument()
  })

  it('is case-insensitive on the status key', () => {
    render(<StatusPill status="SUCCEEDED" />)
    expect(screen.getByText('Succeeded')).toBeInTheDocument()
  })

  it('normalizes both cancelled and canceled spellings to "Canceled"', () => {
    const { rerender } = render(<StatusPill status="cancelled" />)
    expect(screen.getByText('Canceled')).toBeInTheDocument()
    rerender(<StatusPill status="canceled" />)
    expect(screen.getByText('Canceled')).toBeInTheDocument()
  })

  it('falls back to the raw status for an unknown value', () => {
    render(<StatusPill status="weird_state" />)
    expect(screen.getByText('weird_state')).toBeInTheDocument()
  })
})
