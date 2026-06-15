import { describe, expect, it } from 'vitest'
import { layeredLayout, validateDag, type GraphEdge, type GraphNode } from './workflowGraph'

function node(id: string, type_key = 'step.noop', config: Record<string, unknown> = {}): GraphNode {
  return { id, type_key, label: id, config }
}

describe('validateDag', () => {
  const emptySchemas = new Map<string, Record<string, unknown>>()

  it('returns no issues for an empty graph', () => {
    expect(validateDag([], [], emptySchemas)).toEqual([])
  })

  it('flags an unknown step type when schemas are present', () => {
    const schemas = new Map([['step.known', {}]])
    const issues = validateDag([node('a', 'step.mystery')], [], schemas)
    expect(issues).toEqual([
      expect.objectContaining({ level: 'error', nodeId: 'a', message: expect.stringContaining('Unknown step type') }),
    ])
  })

  it('flags missing required config keys', () => {
    const schemas = new Map([['step.x', { required: ['interval_seconds'] }]])
    const issues = validateDag([node('a', 'step.x', {})], [], schemas)
    expect(issues).toEqual([
      expect.objectContaining({ level: 'error', message: expect.stringContaining('interval_seconds') }),
    ])
  })

  it('accepts a node whose required config is supplied', () => {
    const schemas = new Map([['step.x', { required: ['interval_seconds'] }]])
    expect(validateDag([node('a', 'step.x', { interval_seconds: 2 })], [], schemas)).toEqual([])
  })

  it('warns about a disconnected node only when there is more than one node', () => {
    const single = validateDag([node('a')], [], emptySchemas)
    expect(single.find((i) => i.message.includes('not connected'))).toBeUndefined()

    const two = validateDag([node('a'), node('b')], [{ source: 'a', target: 'a' }], emptySchemas)
    expect(two.find((i) => i.level === 'warning' && i.nodeId === undefined)).toBeUndefined()
    expect(two.some((i) => i.message.includes('"b" is not connected'))).toBe(true)
  })

  it('detects a cycle', () => {
    const nodes = [node('a'), node('b')]
    const edges: GraphEdge[] = [
      { source: 'a', target: 'b' },
      { source: 'b', target: 'a' },
    ]
    const issues = validateDag(nodes, edges, emptySchemas)
    expect(issues.some((i) => i.level === 'error' && i.message.includes('cycle'))).toBe(true)
  })

  it('accepts a valid two-step DAG with no issues', () => {
    const nodes = [node('a'), node('b')]
    const edges: GraphEdge[] = [{ source: 'a', target: 'b' }]
    expect(validateDag(nodes, edges, emptySchemas)).toEqual([])
  })
})

describe('layeredLayout', () => {
  it('places a root at layer 0 and its child one column over', () => {
    const pos = layeredLayout([node('a'), node('b')], [{ source: 'a', target: 'b' }])
    expect(pos.get('a')!.x).toBe(0)
    expect(pos.get('b')!.x).toBeGreaterThan(pos.get('a')!.x)
  })

  it('uses longest-path layering for diamond graphs', () => {
    // a -> b -> d and a -> d ; d must sit past b (longest path = 2)
    const nodes = [node('a'), node('b'), node('d')]
    const edges: GraphEdge[] = [
      { source: 'a', target: 'b' },
      { source: 'b', target: 'd' },
      { source: 'a', target: 'd' },
    ]
    const pos = layeredLayout(nodes, edges)
    expect(pos.get('d')!.x).toBeGreaterThan(pos.get('b')!.x)
  })

  it('stacks sibling nodes in the same column on different rows', () => {
    const nodes = [node('a'), node('b'), node('c')]
    const edges: GraphEdge[] = [
      { source: 'a', target: 'b' },
      { source: 'a', target: 'c' },
    ]
    const pos = layeredLayout(nodes, edges)
    expect(pos.get('b')!.x).toBe(pos.get('c')!.x)
    expect(pos.get('b')!.y).not.toBe(pos.get('c')!.y)
  })
})
