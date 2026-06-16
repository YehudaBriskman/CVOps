import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, type RenderOptions } from '@testing-library/react'
import { type ReactElement, type ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'

/** Fresh QueryClient per render with retries off and no caching across tests,
 * so query behaviour is deterministic and failures surface immediately. */
export function makeTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  })
}

interface ProviderOptions extends Omit<RenderOptions, 'wrapper'> {
  route?: string
  queryClient?: QueryClient
}

/** Render a component wrapped in the providers the app relies on (TanStack
 * Query + Router). Returns the RTL result plus the QueryClient for assertions. */
export function renderWithProviders(ui: ReactElement, options: ProviderOptions = {}) {
  const { route = '/', queryClient = makeTestQueryClient(), ...rest } = options

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
      </QueryClientProvider>
    )
  }

  return { queryClient, ...render(ui, { wrapper: Wrapper, ...rest }) }
}

/** Wrapper for renderHook — hooks that use TanStack Query need the provider. */
export function withQueryClient(queryClient: QueryClient = makeTestQueryClient()) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}
