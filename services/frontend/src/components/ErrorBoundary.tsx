import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

/**
 * Top-level error boundary. Catches render-time errors anywhere in the tree so a
 * single broken component can't blank the whole app. Async/data errors are handled
 * separately by the TanStack Query global handlers (see queryClient.ts).
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Surface to the console for local debugging; no remote telemetry yet.
    console.error('Uncaught render error:', error, info.componentStack)
  }

  private reset = (): void => {
    this.setState({ error: null })
  }

  render(): ReactNode {
    if (!this.state.error) return this.props.children

    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-surface-1 p-6 text-center">
        <div className="max-w-md">
          <h1 className="text-lg font-semibold text-text-primary">Something broke</h1>
          <p className="mt-2 text-sm text-text-muted">
            An unexpected error stopped this view from rendering. You can try again or reload the page.
          </p>
          <pre className="mt-4 overflow-auto rounded-lg border border-border bg-surface-2 p-3 text-left text-xs text-text-secondary">
            {this.state.error.message}
          </pre>
          <div className="mt-4 flex justify-center gap-2">
            <button
              type="button"
              onClick={this.reset}
              className="rounded-lg bg-cobalt px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-cobalt-hover"
            >
              Try again
            </button>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="rounded-lg border border-border-strong px-3 py-2 text-sm font-medium text-text-primary transition-colors hover:bg-surface-3"
            >
              Reload
            </button>
          </div>
        </div>
      </div>
    )
  }
}
