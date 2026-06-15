import type { RJSFSchema } from '@rjsf/utils'

/**
 * Derive an rjsf object schema from a training container's `icd_config`.
 *
 * We follow the *implemented* executor's ICD shape (packages/steps train.py
 * `_build_env`): `icd_config.inputs` is a dict keyed by param name, each value
 * `{ "env": "ENV_NAME", ... }`. The executor only reads `.env`; we additionally
 * honour optional UI-only JSON-Schema fields on each entry
 * (`type`, `title`, `default`, `enum`, `description`) purely to generate a typed
 * hyperparameter form. The extension is backward-compatible — train.py ignores
 * these fields.
 *
 * Returns `null` when there are no typed inputs (caller falls back to free-form
 * key/value rows): missing/empty `inputs`, the aspirational legacy *list* shape,
 * or a dict whose entries carry only `env` mappings and no schema fields.
 */
const UI_FIELDS = ['type', 'title', 'default', 'enum', 'description'] as const

export function icdInputsToRjsfSchema(
  icd_config: Record<string, unknown> | null | undefined,
): RJSFSchema | null {
  const inputs = icd_config?.inputs
  // Must be a plain object dict; the legacy list shape (Docker/volume design)
  // is not supported here.
  if (!inputs || typeof inputs !== 'object' || Array.isArray(inputs)) return null

  const properties: Record<string, RJSFSchema> = {}

  for (const [name, raw] of Object.entries(inputs as Record<string, unknown>)) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) continue
    const entry = raw as Record<string, unknown>
    if (!UI_FIELDS.some((f) => f in entry)) continue // pure env mapping → not typed

    const prop: RJSFSchema = {}
    if (typeof entry.type === 'string') prop.type = entry.type as RJSFSchema['type']
    if (typeof entry.title === 'string') prop.title = entry.title
    if ('default' in entry) prop.default = entry.default as RJSFSchema['default']
    if (Array.isArray(entry.enum)) prop.enum = entry.enum as RJSFSchema['enum']
    if (typeof entry.description === 'string') prop.description = entry.description

    properties[name] = prop
  }

  if (Object.keys(properties).length === 0) return null
  return { type: 'object', properties }
}
