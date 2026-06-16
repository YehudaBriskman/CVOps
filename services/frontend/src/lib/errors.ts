/**
 * Narrow an unknown error (typically an AxiosError) to a human-readable string.
 *
 * Handles FastAPI's two error shapes:
 *  - `{ detail: "some message" }` for explicit `HTTPException`s, and
 *  - `{ detail: [{ loc, msg, ... }, ...] }` for Pydantic 422 validation errors.
 *
 * The array form is important: rendering it straight into JSX throws
 * "Objects are not valid as a React child", so it must be flattened to text.
 */
export function errorMessage(error: unknown, fallback = 'An unexpected error occurred'): string {
  if (error && typeof error === 'object') {
    const maybe = error as {
      response?: { data?: { detail?: unknown } }
      message?: unknown
    }
    const detail = maybe.response?.data?.detail

    if (typeof detail === 'string') return detail

    if (Array.isArray(detail)) {
      const messages = detail
        .map(item => {
          if (item && typeof item === 'object' && typeof (item as { msg?: unknown }).msg === 'string') {
            return (item as { msg: string }).msg
          }
          return null
        })
        .filter((m): m is string => m !== null)
      if (messages.length > 0) return messages.join('; ')
    }

    if (typeof maybe.message === 'string') return maybe.message
  }
  return fallback
}
