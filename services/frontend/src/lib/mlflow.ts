// Deep-link into the MLflow tracking UI. The base URL is build-time config
// (VITE_MLFLOW_URL, browser-reachable — e.g. http://localhost:5000); when it's
// unset there's no server to link to, so callers fall back to plain text.
const MLFLOW_URL = import.meta.env.VITE_MLFLOW_URL as string | undefined

/**
 * URL of a specific MLflow run. `experimentId` defaults to "0" only because the
 * UI route requires one; pass the trainer-reported experiment id when known so
 * the link lands on the right experiment.
 */
export function mlflowRunUrl(runId: string, experimentId: string | number = '0'): string | null {
  if (!MLFLOW_URL) return null
  return `${MLFLOW_URL}/#/experiments/${experimentId}/runs/${runId}`
}
