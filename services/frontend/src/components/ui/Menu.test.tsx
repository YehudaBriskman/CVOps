import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Menu, MenuItem } from './Menu'

describe('Menu', () => {
  it('stays closed until the trigger is clicked, then fires the item handler', () => {
    const onLogout = vi.fn()
    render(
      <Menu triggerLabel="Account menu" triggerContent="U">
        <MenuItem onClick={onLogout}>Log out</MenuItem>
      </Menu>,
    )

    const trigger = screen.getByLabelText('Account menu')
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('menu')).toBeNull()
    // The destructive action must not fire just by rendering / clicking the avatar.
    expect(onLogout).not.toHaveBeenCalled()

    fireEvent.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('menu')).toBeInTheDocument()
    expect(onLogout).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('menuitem', { name: 'Log out' }))
    expect(onLogout).toHaveBeenCalledTimes(1)
  })

  it('closes on Escape', () => {
    render(
      <Menu triggerLabel="Account menu" triggerContent="U">
        <MenuItem>Log out</MenuItem>
      </Menu>,
    )
    fireEvent.click(screen.getByLabelText('Account menu'))
    expect(screen.getByRole('menu')).toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('menu')).toBeNull()
  })
})
