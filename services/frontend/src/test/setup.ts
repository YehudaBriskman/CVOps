/// <reference types="vitest/globals" />
import '@testing-library/jest-dom/vitest'

// This jsdom build ships an incomplete Storage (no `clear`) and a Blob without
// `arrayBuffer`/`stream`. Both exist in every real browser, so we backfill them
// here rather than weaken the tests to dodge the gap.

class MemoryStorage implements Storage {
  private map = new Map<string, string>()
  get length() {
    return this.map.size
  }
  clear() {
    this.map.clear()
  }
  getItem(key: string) {
    return this.map.has(key) ? this.map.get(key)! : null
  }
  key(index: number) {
    return [...this.map.keys()][index] ?? null
  }
  removeItem(key: string) {
    this.map.delete(key)
  }
  setItem(key: string, value: string) {
    this.map.set(key, String(value))
  }
}

Object.defineProperty(globalThis, 'localStorage', { value: new MemoryStorage(), configurable: true })

if (typeof Blob.prototype.arrayBuffer !== 'function') {
  // jsdom's Blob can't read its own bytes back. node's Buffer-backed Blob is
  // spec-correct (arrayBuffer/stream) and is what crypto.subtle consumes, so we
  // swap the global implementation wholesale.
  const { Blob: NodeBlob } = await import('node:buffer')
  Object.defineProperty(globalThis, 'Blob', { value: NodeBlob, configurable: true, writable: true })
  if (typeof window !== 'undefined') {
    Object.defineProperty(window, 'Blob', { value: NodeBlob, configurable: true, writable: true })
  }
}
