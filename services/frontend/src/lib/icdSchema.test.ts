import { describe, expect, it } from 'vitest'
import { icdInputsToRjsfSchema } from './icdSchema'

describe('icdInputsToRjsfSchema', () => {
  it('maps a typed dict input into an rjsf object schema', () => {
    const schema = icdInputsToRjsfSchema({
      inputs: {
        epochs: {
          env: 'EPOCHS',
          type: 'integer',
          title: 'Epochs',
          default: 50,
          description: 'Number of passes',
        },
      },
    })
    expect(schema).toEqual({
      type: 'object',
      properties: {
        epochs: {
          type: 'integer',
          title: 'Epochs',
          default: 50,
          description: 'Number of passes',
        },
      },
    })
  })

  it('carries enums through', () => {
    const schema = icdInputsToRjsfSchema({
      inputs: { optimizer: { env: 'OPT', type: 'string', enum: ['adam', 'sgd'] } },
    })
    expect(schema?.properties?.optimizer).toEqual({ type: 'string', enum: ['adam', 'sgd'] })
  })

  it('skips pure env mappings but keeps typed siblings', () => {
    const schema = icdInputsToRjsfSchema({
      inputs: {
        seed: { env: 'SEED' }, // no schema fields → dropped
        epochs: { env: 'EPOCHS', type: 'integer' },
      },
    })
    expect(Object.keys(schema?.properties ?? {})).toEqual(['epochs'])
  })

  it('returns null when no input is typed', () => {
    expect(icdInputsToRjsfSchema({ inputs: { epochs: { env: 'EPOCHS' } } })).toBeNull()
  })

  it('returns null for missing / empty inputs', () => {
    expect(icdInputsToRjsfSchema(undefined)).toBeNull()
    expect(icdInputsToRjsfSchema(null)).toBeNull()
    expect(icdInputsToRjsfSchema({})).toBeNull()
    expect(icdInputsToRjsfSchema({ inputs: {} })).toBeNull()
  })

  it('returns null for the legacy list shape', () => {
    expect(
      icdInputsToRjsfSchema({
        inputs: [{ name: 'data', type: 'volume', mount: '/data' }],
      }),
    ).toBeNull()
  })
})
