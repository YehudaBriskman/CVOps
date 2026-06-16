import { setupServer } from 'msw/node'
import { handlers } from './handlers'

// Shared MSW server. Tests add per-case overrides with `server.use(...)`.
export const server = setupServer(...handlers)
