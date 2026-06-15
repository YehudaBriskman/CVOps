/**
 * PUT a file to a presigned URL while reporting byte-level upload progress.
 *
 * `fetch` cannot surface upload progress (no `ReadableStream` request body in
 * browsers), so we drop to `XMLHttpRequest`, whose `upload.onprogress` gives us
 * `loaded`/`total`. Used for the direct-to-storage blob upload in the data
 * source flow.
 *
 * `onProgress` receives a fraction in [0, 1], or `null` when the total size is
 * not known (the caller can show an indeterminate state).
 */
export function putWithProgress(
  url: string,
  file: Blob,
  onProgress?: (fraction: number | null) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('PUT', url)

    xhr.upload.onprogress = (e) => {
      onProgress?.(e.lengthComputable ? e.loaded / e.total : null)
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve()
      else reject(new Error(`Upload failed: ${xhr.status}`))
    }
    xhr.onerror = () => reject(new Error('Upload failed: network error'))
    xhr.onabort = () => reject(new Error('Upload aborted'))

    xhr.send(file)
  })
}
