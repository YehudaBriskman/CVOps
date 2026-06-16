import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { AnnotationBox } from '../../api/annotations'
import { BoxOverlay } from './BoxOverlay'

const box = (class_key: string, coords: number[]): AnnotationBox => ({
  class_key,
  geometry: { coords },
})

describe('BoxOverlay', () => {
  it('positions a box by percentage from center-format coords', () => {
    const { getByText } = render(<BoxOverlay boxes={[box('car', [0.5, 0.5, 0.2, 0.2])]} />)
    // label sits inside the box div
    const boxDiv = getByText('car').parentElement as HTMLElement
    expect(boxDiv.style.left).toBe('40%') // (0.5 - 0.1) * 100
    expect(boxDiv.style.top).toBe('40%')
    expect(boxDiv.style.width).toBe('20%')
    expect(boxDiv.style.height).toBe('20%')
  })

  it('renders the class key as the label', () => {
    const { getByText } = render(<BoxOverlay boxes={[box('person', [0.1, 0.1, 0.1, 0.1])]} />)
    expect(getByText('person')).toBeInTheDocument()
  })

  it('skips malformed boxes (coords length !== 4)', () => {
    const { queryByText } = render(
      <BoxOverlay
        boxes={[box('ok', [0.5, 0.5, 0.2, 0.2]), box('bad', [0.1, 0.2, 0.3])]}
      />,
    )
    expect(queryByText('ok')).toBeInTheDocument()
    expect(queryByText('bad')).not.toBeInTheDocument()
  })

  it('gives the same class the same color across renders', () => {
    const { getByText } = render(<BoxOverlay boxes={[box('car', [0.5, 0.5, 0.2, 0.2])]} />)
    const label = getByText('car')
    const boxDiv = label.parentElement as HTMLElement
    // border color and label background are the same deterministic class color
    // (jsdom normalizes the hsl() literal to rgb(), so just assert equality).
    expect(boxDiv.style.borderColor).toBeTruthy()
    expect(label.style.backgroundColor).toBe(boxDiv.style.borderColor)
  })

  it('renders nothing for an empty box list', () => {
    const { container } = render(<BoxOverlay boxes={[]} />)
    // only the wrapper div, no box children
    expect(container.querySelectorAll('.border-2')).toHaveLength(0)
  })
})
