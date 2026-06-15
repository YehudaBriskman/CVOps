import { QueryClient, QueryCache, MutationCache } from '@tanstack/react-query'
import { toast } from '../store/toast'

/** Narrow an unknown error (typically an AxiosError) to a human-readable message. */
function errorMessage(error: unknown): string {
  if (error && typeof error === 'object') {
    const maybe = error as {
      response?: { data?: { detail?: unknown } }
      message?: unknown
    }
    const detail = maybe.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (typeof maybe.message === 'string') return maybe.message
  }
  return 'An unexpected error occurred'
}

/** HTTP status of an unknown error, if it looks like an Axios response error. */
function errorStatus(error: unknown): number | undefined {
  if (error && typeof error === 'object') {
    const status = (error as { response?: { status?: unknown } }).response?.status
    if (typeof status === 'number') return status
  }
  return undefined
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        const status = errorStatus(error)
        // Never retry client errors (4xx); they won't fix themselves.
        if (status !== undefined && status >= 400 && status < 500) return false
        return failureCount < 2
      },
    },
    mutations: {
      retry: false,
    },
  },
  queryCache: new QueryCache({
    onError: (error, query) => {
      // 401s are handled by the axios refresh interceptor; don't double-toast.
      if (errorStatus(error) === 401) return
      if (query.meta?.silent) return
      toast.error('Failed to load', errorMessage(error))
    },
  }),
  mutationCache: new MutationCache({
    onError: (error, _vars, _ctx, mutation) => {
      if (errorStatus(error) === 401) return
      if (mutation.meta?.silent) return
      toast.error('Action failed', errorMessage(error))
    },
  }),
})
