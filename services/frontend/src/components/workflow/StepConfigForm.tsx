import Form, { type IChangeEvent } from '@rjsf/core'
import validator from '@rjsf/validator-ajv8'
import type { RJSFSchema, UiSchema } from '@rjsf/utils'

// Hide rjsf's built-in submit button — config is saved with the whole workflow.
const UI_SCHEMA: UiSchema = { 'ui:submitButtonOptions': { norender: true } }

function isEmptySchema(schema: Record<string, unknown>): boolean {
  const props = schema.properties
  return !props || (typeof props === 'object' && Object.keys(props).length === 0)
}

/**
 * Auto-generated config form for a workflow step, driven by the step's JSON
 * Schema from GET /registry/types. No hand-written form per step type.
 */
export function StepConfigForm({
  schema,
  formData,
  onChange,
}: {
  schema: Record<string, unknown>
  formData: Record<string, unknown>
  onChange: (data: Record<string, unknown>) => void
}) {
  if (isEmptySchema(schema)) {
    return <p className="text-sm text-text-muted">This step has no configurable parameters.</p>
  }

  return (
    <div className="cvops-rjsf">
      <Form
        schema={schema as RJSFSchema}
        uiSchema={UI_SCHEMA}
        formData={formData}
        validator={validator}
        liveValidate
        showErrorList={false}
        onChange={(e: IChangeEvent) => onChange((e.formData ?? {}) as Record<string, unknown>)}
      />
    </div>
  )
}
