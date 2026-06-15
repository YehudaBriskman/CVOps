/**
 * Pure graph helpers for the workflow canvas: DAG validation and a
 * dependency-free layered auto-layout. No React or react-flow types here so
 * these stay unit-testable and reusable.
 */

export interface GraphNode {
  id: string
  type_key: string
  label: string
  config: Record<string, unknown>
}

export interface GraphEdge {
  source: string
  target: string
}

export interface DagIssue {
  level: 'error' | 'warning'
  message: string
  nodeId?: string
}

/** Required-config keys declared in a step's JSON Schema. */
function requiredKeys(schema: Record<string, unknown> | undefined): string[] {
  if (!schema) return []
  const req = schema.required
  return Array.isArray(req) ? req.filter((k): k is string => typeof k === 'string') : []
}

function isMissing(value: unknown): boolean {
  return value === undefined || value === null || value === ''
}

/**
 * Validate a workflow graph. `schemaByType` maps a step type_key to its JSON
 * Schema; pass an empty map to skip type/config checks (e.g. registry offline).
 */
export function validateDag(
  nodes: GraphNode[],
  edges: GraphEdge[],
  schemaByType: Map<string, Record<string, unknown>>,
): DagIssue[] {
  const issues: DagIssue[] = []
  if (nodes.length === 0) return issues

  const ids = new Set(nodes.map((n) => n.id))
  const haveSchemas = schemaByType.size > 0

  // Unknown step types + missing required config.
  for (const n of nodes) {
    const schema = schemaByType.get(n.type_key)
    if (haveSchemas && !schema) {
      issues.push({ level: 'error', message: `Unknown step type "${n.type_key}"`, nodeId: n.id })
      continue
    }
    for (const key of requiredKeys(schema)) {
      if (isMissing(n.config?.[key])) {
        issues.push({
          level: 'error',
          message: `"${n.label}" is missing required config "${key}"`,
          nodeId: n.id,
        })
      }
    }
  }

  // Orphan nodes (not connected to anything) only matter once there's >1 step.
  if (nodes.length > 1) {
    const connected = new Set<string>()
    for (const e of edges) {
      if (ids.has(e.source)) connected.add(e.source)
      if (ids.has(e.target)) connected.add(e.target)
    }
    for (const n of nodes) {
      if (!connected.has(n.id)) {
        issues.push({ level: 'warning', message: `"${n.label}" is not connected`, nodeId: n.id })
      }
    }
  }

  // Cycle detection via Kahn's algorithm — the engine runs a topo sort, so a
  // cycle would never execute.
  const indegree = new Map<string, number>()
  const adj = new Map<string, string[]>()
  for (const n of nodes) {
    indegree.set(n.id, 0)
    adj.set(n.id, [])
  }
  for (const e of edges) {
    if (!ids.has(e.source) || !ids.has(e.target)) continue
    adj.get(e.source)!.push(e.target)
    indegree.set(e.target, (indegree.get(e.target) ?? 0) + 1)
  }
  const queue = nodes.filter((n) => (indegree.get(n.id) ?? 0) === 0).map((n) => n.id)
  let processed = 0
  while (queue.length > 0) {
    const id = queue.shift()!
    processed++
    for (const next of adj.get(id) ?? []) {
      const d = (indegree.get(next) ?? 0) - 1
      indegree.set(next, d)
      if (d === 0) queue.push(next)
    }
  }
  if (processed < nodes.length) {
    issues.push({ level: 'error', message: 'Workflow has a cycle — steps must form a DAG' })
  }

  return issues
}

export interface Position {
  x: number
  y: number
}

const LAYER_GAP = 260
const ROW_GAP = 130

/**
 * Layered left-to-right layout. Each node's column is its longest path from a
 * root (longest-path layering); rows pack nodes within a column in input order.
 * Falls back gracefully on cyclic graphs by capping the layer at node count.
 */
export function layeredLayout(nodes: GraphNode[], edges: GraphEdge[]): Map<string, Position> {
  const ids = new Set(nodes.map((n) => n.id))
  const incoming = new Map<string, string[]>()
  for (const n of nodes) incoming.set(n.id, [])
  for (const e of edges) {
    if (ids.has(e.source) && ids.has(e.target)) incoming.get(e.target)!.push(e.source)
  }

  const layer = new Map<string, number>()
  const visiting = new Set<string>()

  function computeLayer(id: string): number {
    const cached = layer.get(id)
    if (cached !== undefined) return cached
    if (visiting.has(id)) return 0 // cycle guard
    visiting.add(id)
    const parents = incoming.get(id) ?? []
    const value = parents.length === 0 ? 0 : Math.min(
      nodes.length - 1,
      Math.max(...parents.map((p) => computeLayer(p) + 1)),
    )
    visiting.delete(id)
    layer.set(id, value)
    return value
  }
  for (const n of nodes) computeLayer(n.id)

  // Group by layer, preserving node order for stable rows.
  const byLayer = new Map<number, string[]>()
  for (const n of nodes) {
    const l = layer.get(n.id) ?? 0
    if (!byLayer.has(l)) byLayer.set(l, [])
    byLayer.get(l)!.push(n.id)
  }

  const positions = new Map<string, Position>()
  for (const [l, rowIds] of byLayer) {
    rowIds.forEach((id, row) => {
      positions.set(id, { x: l * LAYER_GAP, y: row * ROW_GAP })
    })
  }
  return positions
}
