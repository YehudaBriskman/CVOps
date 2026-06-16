import { describe, expect, it } from 'vitest'
import { sha256Hex } from './hash'

// jsdom exposes crypto.subtle, so this exercises the fast secure-context path.
describe('sha256Hex', () => {
  it('hashes an empty blob to the known SHA-256 of empty input', async () => {
    const empty = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
    expect(await sha256Hex(new Blob([]))).toBe(empty)
  })

  it('hashes "abc" to the known SHA-256 vector', async () => {
    const abc = 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
    expect(await sha256Hex(new Blob(['abc']))).toBe(abc)
  })

  it('returns a 64-char lowercase hex string', async () => {
    const hex = await sha256Hex(new Blob(['some content']))
    expect(hex).toMatch(/^[0-9a-f]{64}$/)
  })

  it('is deterministic for identical content', async () => {
    const a = await sha256Hex(new Blob(['repeatable']))
    const b = await sha256Hex(new Blob(['repeatable']))
    expect(a).toBe(b)
  })
})
