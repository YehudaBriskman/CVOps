import { STEP_META } from './stepMeta'

export type StepTypeDef = {
  type_key: string
  label: string
  description: string
  color: string
}

/** Fallback palette when the registry is unavailable — derived from STEP_META. */
export const STEP_TYPES: StepTypeDef[] = Object.entries(STEP_META).map(([type_key, m]) => ({
  type_key,
  label: m.label,
  description: m.blurb,
  color: m.color,
}))
