/**
 * Render an arbitrary JSON value for display. Numbers are trimmed to a sensible
 * precision; objects/arrays (e.g. a metrics blob's nested `best_params`) become
 * compact JSON instead of the useless "[object Object]" that `String(v)` gives.
 */
export function formatValue(v: unknown): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'number') {
    return Number.isInteger(v) ? String(v) : Number(v.toPrecision(4)).toString()
  }
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}
