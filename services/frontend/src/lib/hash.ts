/**
 * SHA-256 of a file, returned as a lowercase hex string.
 *
 * The Web Crypto API (`crypto.subtle`) is only exposed in *secure contexts* —
 * HTTPS or `http://localhost`. Over plain HTTP on a non-localhost origin (e.g.
 * a dev VM at `http://10.0.0.5`) it is `undefined`, which previously crashed the
 * upload flow with "can't access property digest, crypto.subtle is undefined".
 *
 * So we use the native digest when available (fast, zero bundle cost), and fall
 * back to a chunked hash-wasm implementation otherwise. The fallback streams the
 * file in chunks rather than buffering the whole video into memory.
 */
export async function sha256Hex(file: Blob): Promise<string> {
  const subtle = globalThis.crypto?.subtle
  if (subtle) {
    // Wrap in a fresh Uint8Array (a current-realm TypedArray view) before
    // digesting: a bare ArrayBuffer crossing realms — e.g. jsdom's Blob vs the
    // Node WebCrypto in tests — is rejected as "not an instance of ArrayBuffer".
    const bytes = new Uint8Array(await file.arrayBuffer())
    const digest = await subtle.digest('SHA-256', bytes)
    return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('')
  }

  // Insecure context: load the WASM hasher lazily so secure-context users never
  // pay for it, and feed the file through in chunks.
  const { createSHA256 } = await import('hash-wasm')
  const hasher = await createSHA256()
  hasher.init()
  if (typeof file.stream === 'function') {
    const reader = file.stream().getReader()
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      hasher.update(value)
    }
  } else {
    // No streaming (very old browsers, or non-browser test envs): buffer once.
    hasher.update(new Uint8Array(await file.arrayBuffer()))
  }
  return hasher.digest('hex')
}
