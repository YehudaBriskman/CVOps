import { describe, expect, it } from 'vitest'
import { cn } from './cn'

describe('cn', () => {
  it('joins multiple class names', () => {
    expect(cn('a', 'b', 'c')).toBe('a b c')
  })

  it('drops falsy conditional classes', () => {
    // eslint-disable-next-line no-constant-binary-expression -- exercises the `cond && cls` drop path with a literal
    expect(cn('base', false && 'hidden', null, undefined, 'shown')).toBe('base shown')
  })

  it('de-dupes conflicting tailwind utilities, keeping the last', () => {
    expect(cn('px-2', 'px-4')).toBe('px-4')
    expect(cn('text-red-500', 'text-blue-500')).toBe('text-blue-500')
  })

  it('merges object and array inputs like clsx', () => {
    expect(cn(['a', { b: true, c: false }], 'd')).toBe('a b d')
  })

  it('returns an empty string with no inputs', () => {
    expect(cn()).toBe('')
  })
})
