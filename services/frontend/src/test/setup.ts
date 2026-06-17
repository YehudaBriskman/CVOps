import { webcrypto } from 'node:crypto'
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { server } from './server'

// jsdom does not implement crypto.subtle, and whether the Node WebCrypto global
// survives into each jsdom worker is non-deterministic. Pin it so the
// secure-context hash path (lib/hash.ts) is the one tests exercise everywhere,
// instead of falling back to file.stream() which jsdom also lacks.
if (typeof globalThis.crypto?.subtle === 'undefined') {
  Object.defineProperty(globalThis, 'crypto', { value: webcrypto, configurable: true })
}

// jsdom 29 does not always expose localStorage as a usable global — under an
// opaque origin it surfaces as an empty `{}` (defined, but `getItem`/`clear`
// are not functions) rather than undefined. Provide a minimal in-memory Storage
// whenever the global is missing OR non-functional, so app code
// (lib/client.ts, api/auth.ts) and tests can use `localStorage` unconditionally.
if (typeof globalThis.localStorage?.getItem !== 'function') {
  class MemoryStorage implements Storage {
    private store = new Map<string, string>()
    get length() {
      return this.store.size
    }
    clear() {
      this.store.clear()
    }
    getItem(key: string) {
      return this.store.has(key) ? this.store.get(key)! : null
    }
    key(i: number) {
      return Array.from(this.store.keys())[i] ?? null
    }
    removeItem(key: string) {
      this.store.delete(key)
    }
    setItem(key: string, value: string) {
      this.store.set(key, String(value))
    }
  }
  const mem = new MemoryStorage()
  Object.defineProperty(globalThis, 'localStorage', { value: mem, configurable: true })
  if (typeof window !== 'undefined') {
    Object.defineProperty(window, 'localStorage', { value: mem, configurable: true })
  }
}

// MSW lifecycle. onUnhandledRequest 'error' forces every test to declare the
// network it depends on — an unmocked call fails loudly rather than hitting a
// real host.
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))

afterEach(() => {
  server.resetHandlers()
  cleanup()
  localStorage.clear()
})

afterAll(() => server.close())

// jsdom lacks matchMedia; some UI components probe it. Provide a no-op stub.
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList
}
