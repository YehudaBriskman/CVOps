import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { EmptyState, ErrorState } from './States'

describe('EmptyState', () => {
  it('renders the title and optional description and action', () => {
    render(<EmptyState title="No data" description="Upload one" action={<button>Add</button>} />)
    expect(screen.getByText('No data')).toBeInTheDocument()
    expect(screen.getByText('Upload one')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add' })).toBeInTheDocument()
  })

  it('omits the description when not provided', () => {
    render(<EmptyState title="Nothing here" />)
    expect(screen.getByText('Nothing here')).toBeInTheDocument()
    expect(screen.queryByText('Upload one')).not.toBeInTheDocument()
  })
})

describe('ErrorState', () => {
  it('exposes an alert role and a default title', () => {
    render(<ErrorState />)
    const alert = screen.getByRole('alert')
    expect(alert).toBeInTheDocument()
    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
  })

  it('renders the retry button only when onRetry is supplied and fires it on click', async () => {
    const onRetry = vi.fn()
    const { rerender } = render(<ErrorState description="boom" />)
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()

    rerender(<ErrorState description="boom" onRetry={onRetry} />)
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })
})
