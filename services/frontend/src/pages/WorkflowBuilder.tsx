import { useCallback, useMemo, useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  ReactFlowProvider,
  useNodesState,
  useEdgesState,
  useReactFlow,
  BackgroundVariant,
} from '@xyflow/react'
import type { Connection, Edge } from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { StepNode } from '../components/workflow/StepNode'
import type { StepNodeType } from '../components/workflow/StepNode'
import { StepPalette } from '../components/workflow/StepPalette'
import { StepConfigForm } from '../components/workflow/StepConfigForm'
import { useWorkflow, useUpdateWorkflow } from '../api/workflows'
import { useCreateRun } from '../api/runs'
import { useRegistryTypes } from '../api/registry'
import { usePinProject } from '../lib/useActiveProject'
import { STEP_TYPES } from '../lib/stepCatalog'
import { Button, Drawer, Field, Input } from '../components/ui'
import { toast } from '../store/toast'
import { validateDag, layeredLayout, type GraphNode, type GraphEdge } from '../lib/workflowGraph'

const MINIMAP_COLORS: Record<string, string> = {
  'step.extract_frames': '#3b82f6',
  'step.auto_label':     '#a855f7',
  'step.human_review':   '#f97316',
  'step.commit_dataset': '#16a34a',
  'step.export_yolo':    '#eab308',
  'step.train':          '#ef4444',
}

function defToNodes(definition: Record<string, unknown>): StepNodeType[] {
  const steps = (definition.steps as Array<Record<string, unknown>>) ?? []
  return steps.map((s, i) => ({
    id: String(s.id ?? `step-${i}`),
    type: 'step',
    position: (s.position as { x: number; y: number }) ?? { x: i * 240, y: 150 },
    data: {
      label: String(s.label ?? s.type ?? 'Step'),
      type_key: String(s.type ?? ''),
      status: null,
      config: (s.config as Record<string, unknown>) ?? {},
    },
  }))
}

function defToEdges(definition: Record<string, unknown>): Edge[] {
  const edges = (definition.edges as Array<Record<string, unknown>>) ?? []
  return edges.map((e, i) => ({
    id: String(e.id ?? `e${i}`),
    source: String(e.source ?? e.from ?? ''),
    target: String(e.target ?? e.to ?? ''),
  }))
}

function nodesToDef(
  nodes: StepNodeType[],
  edges: Edge[],
): Record<string, unknown> {
  return {
    steps: nodes.map(n => ({
      id: n.id,
      type: n.data.type_key,
      label: n.data.label,
      position: n.position,
      config: n.data.config ?? {},
    })),
    edges: edges.map(e => ({ id: e.id, source: e.source, target: e.target })),
  }
}

function FlowCanvas({ workflowId }: { workflowId: string }) {
  const navigate = useNavigate()
  const { data: workflow } = useWorkflow(workflowId)
  const updateWorkflow = useUpdateWorkflow(workflowId)
  const createRun = useCreateRun()
  const { data: registryTypes } = useRegistryTypes('step')
  const { screenToFlowPosition } = useReactFlow()

  const [nodes, setNodes, onNodesChange] = useNodesState<StepNodeType>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const [loaded, setLoaded] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const [showIssues, setShowIssues] = useState(false)

  const selectedNode = nodes.find(n => n.id === selectedId) ?? null
  const selectedType = registryTypes?.find(rt => rt.type_key === selectedNode?.data.type_key)

  const schemaByType = useMemo(() => {
    const m = new Map<string, Record<string, unknown>>()
    for (const rt of registryTypes ?? []) m.set(rt.type_key, rt.json_schema)
    return m
  }, [registryTypes])

  const graph = useMemo(() => {
    const gNodes: GraphNode[] = nodes.map(n => ({
      id: n.id,
      type_key: n.data.type_key,
      label: n.data.label,
      config: n.data.config ?? {},
    }))
    const gEdges: GraphEdge[] = edges.map(e => ({ source: e.source, target: e.target }))
    return { gNodes, gEdges }
  }, [nodes, edges])

  const issues = useMemo(
    () => validateDag(graph.gNodes, graph.gEdges, schemaByType),
    [graph, schemaByType],
  )
  const errorCount = issues.filter(i => i.level === 'error').length

  const handleTidy = useCallback(() => {
    const pos = layeredLayout(graph.gNodes, graph.gEdges)
    setNodes(nds => nds.map(n => (pos.has(n.id) ? { ...n, position: pos.get(n.id)! } : n)))
  }, [graph, setNodes])

  const onNodeClick = useCallback(
    (_e: React.MouseEvent, node: StepNodeType) => setSelectedId(node.id),
    [],
  )

  const patchNodeData = useCallback(
    (id: string, patch: Partial<StepNodeType['data']>) => {
      setNodes(nds => nds.map(n => (n.id === id ? { ...n, data: { ...n.data, ...patch } } : n)))
    },
    [setNodes],
  )

  const deleteNode = useCallback(
    (id: string) => {
      setNodes(nds => nds.filter(n => n.id !== id))
      setEdges(eds => eds.filter(e => e.source !== id && e.target !== id))
      setSelectedId(null)
    },
    [setNodes, setEdges],
  )

  useEffect(() => {
    if (workflow && !loaded) {
      setNodes(defToNodes(workflow.definition))
      setEdges(defToEdges(workflow.definition))
      setLoaded(true)
    }
  }, [workflow, loaded, setNodes, setEdges])

  const nodeTypes = useMemo(() => ({ step: StepNode }), [])

  const paletteSteps = useMemo(() => {
    if (registryTypes && registryTypes.length > 0) {
      return registryTypes.map(rt => ({
        type_key: rt.type_key,
        label: rt.ui_hints.description
          ? String(rt.ui_hints.description).replace(/\..+/, '')
          : rt.type_key.replace('step.', '').replace(/_/g, ' '),
        description: String(rt.ui_hints.description ?? ''),
        accent: MINIMAP_COLORS[rt.type_key]
          ? `bg-[${MINIMAP_COLORS[rt.type_key]}]`
          : 'bg-slate-500',
      }))
    }
    return STEP_TYPES
  }, [registryTypes])

  const onConnect = useCallback(
    (params: Connection) => setEdges(eds => addEdge(params, eds)),
    [setEdges],
  )

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      const typeKey = e.dataTransfer.getData('application/xyflow')
      if (!typeKey) return
      const position = screenToFlowPosition({ x: e.clientX, y: e.clientY })
      const step = paletteSteps.find(s => s.type_key === typeKey)
      setNodes(nds => [
        ...nds,
        {
          id: `${typeKey}-${Date.now()}`,
          type: 'step',
          position,
          data: { label: step?.label ?? typeKey, type_key: typeKey, status: null },
        },
      ])
    },
    [screenToFlowPosition, setNodes, paletteSteps],
  )

  async function handleSave() {
    try {
      const wf = await updateWorkflow.mutateAsync({ definition: nodesToDef(nodes, edges) })
      toast.success('Workflow saved', `Now at v${wf.version}`)
    } catch {
      // Surfaced by the global mutation error handler (toast).
    }
  }

  async function handleRun() {
    try {
      const run = await createRun.mutateAsync({ workflowId })
      navigate(`/runs/${run.id}`)
    } catch {
      // Surfaced by the global mutation error handler (toast).
    }
  }

  return (
    <div className="relative flex-1">
      <div className="absolute right-4 top-4 z-10 flex gap-2">
        <Button variant="secondary" onClick={handleTidy} disabled={nodes.length === 0} className="shadow-sm">
          Tidy
        </Button>
        <Button variant="secondary" onClick={handleSave} loading={updateWorkflow.isPending} className="shadow-sm">
          Save
        </Button>
        <Button
          onClick={handleRun}
          loading={createRun.isPending}
          disabled={errorCount > 0 || nodes.length === 0}
          title={errorCount > 0 ? 'Fix validation errors before running' : undefined}
          className="shadow-sm"
        >
          ▶ Run Workflow
        </Button>
      </div>

      {nodes.length > 0 && (
        <div className="absolute bottom-4 left-4 z-10 max-w-sm">
          {issues.length === 0 ? (
            <div className="rounded-lg border border-border bg-surface-2 px-3 py-1.5 text-xs font-medium text-success shadow-sm">
              ✓ Valid DAG · {nodes.length} step{nodes.length === 1 ? '' : 's'}
            </div>
          ) : (
            <div className="overflow-hidden rounded-lg border border-border bg-surface-2 shadow-sm">
              <button
                type="button"
                onClick={() => setShowIssues(v => !v)}
                className="flex w-full items-center gap-2 px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-surface-3"
              >
                <span
                  aria-hidden
                  className="h-1.5 w-1.5 rounded-full"
                  style={{ backgroundColor: errorCount > 0 ? '#EF4444' : '#F59E0B' }}
                />
                {issues.length} issue{issues.length === 1 ? '' : 's'}
                {errorCount > 0 && ` · ${errorCount} blocking`}
                <span className="ml-1 text-text-muted">{showIssues ? '▾' : '▸'}</span>
              </button>
              {showIssues && (
                <ul className="border-t border-border">
                  {issues.map((issue, i) => (
                    <li key={i}>
                      <button
                        type="button"
                        onClick={() => issue.nodeId && setSelectedId(issue.nodeId)}
                        className="flex w-full items-start gap-2 px-3 py-1.5 text-left text-xs text-text-secondary hover:bg-surface-3"
                      >
                        <span style={{ color: issue.level === 'error' ? '#EF4444' : '#F59E0B' }}>
                          {issue.level === 'error' ? '✕' : '!'}
                        </span>
                        <span>{issue.message}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        nodeTypes={nodeTypes}
        onDrop={onDrop}
        onDragOver={onDragOver}
        fitView
        fitViewOptions={{ padding: 0.3 }}
      >
        <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="#23262E" />
        <Controls />
        <MiniMap
          nodeColor={node => MINIMAP_COLORS[(node.data as StepNodeType['data']).type_key] ?? '#94a3b8'}
        />
      </ReactFlow>

      <Drawer
        open={selectedNode !== null}
        onClose={() => setSelectedId(null)}
        title={selectedNode ? `Configure · ${selectedNode.data.type_key.replace('step.', '')}` : ''}
      >
        {selectedNode && (
          <div className="space-y-5">
            <Field label="Step label" htmlFor="step-label">
              <Input
                id="step-label"
                value={selectedNode.data.label}
                onChange={e => patchNodeData(selectedNode.id, { label: e.target.value })}
              />
            </Field>

            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-muted">
                Configuration
              </p>
              {selectedType ? (
                <StepConfigForm
                  schema={selectedType.json_schema}
                  formData={selectedNode.data.config ?? {}}
                  onChange={config => patchNodeData(selectedNode.id, { config })}
                />
              ) : (
                <p className="text-sm text-text-muted">
                  Schema unavailable — the step registry could not be loaded.
                </p>
              )}
            </div>

            <div className="flex justify-between border-t border-border pt-4">
              <Button
                variant="ghost"
                size="sm"
                className="text-error hover:text-error"
                onClick={() => deleteNode(selectedNode.id)}
              >
                Delete step
              </Button>
              <Button variant="secondary" size="sm" onClick={() => setSelectedId(null)}>
                Done
              </Button>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  )
}

export default function WorkflowBuilder() {
  const { id } = useParams<{ id: string }>()
  const { data: workflow } = useWorkflow(id)
  const { data: registryTypes } = useRegistryTypes('step')
  usePinProject(workflow?.project_id)

  const paletteSteps = useMemo(() => {
    if (registryTypes && registryTypes.length > 0) {
      return registryTypes.map(rt => ({
        type_key: rt.type_key,
        label: rt.ui_hints.description
          ? String(rt.ui_hints.description).replace(/\..+/, '')
          : rt.type_key.replace('step.', '').replace(/_/g, ' '),
        description: String(rt.ui_hints.description ?? ''),
        accent: 'bg-slate-500',
      }))
    }
    return STEP_TYPES
  }, [registryTypes])

  return (
    <div className="flex" style={{ height: 'calc(100vh - 56px)' }}>
      <StepPalette steps={paletteSteps} />
      {id && workflow && (
        <ReactFlowProvider>
          <FlowCanvas workflowId={id} />
        </ReactFlowProvider>
      )}
      {!workflow && (
        <div className="flex-1 flex items-center justify-center text-text-muted text-sm">
          Loading workflow…
        </div>
      )}
    </div>
  )
}
