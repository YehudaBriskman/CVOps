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
import { useWorkflow, useUpdateWorkflow } from '../api/workflows'
import { useCreateRun } from '../api/runs'
import { useRegistryTypes } from '../api/registry'
import { STEP_TYPES } from '../lib/stepCatalog'

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
      config: {},
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
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle')

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
    setSaveStatus('saving')
    try {
      await updateWorkflow.mutateAsync({ definition: nodesToDef(nodes, edges) })
      setSaveStatus('saved')
      setTimeout(() => setSaveStatus('idle'), 2000)
    } catch {
      setSaveStatus('idle')
    }
  }

  async function handleRun() {
    const run = await createRun.mutateAsync({ workflowId })
    navigate(`/runs/${run.id}`)
  }

  return (
    <div className="flex-1 relative">
      <div className="absolute top-4 right-4 z-10 flex gap-2">
        <button
          onClick={handleSave}
          disabled={updateWorkflow.isPending}
          className="bg-white border border-slate-300 text-slate-700 px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-50 shadow-sm transition-colors disabled:opacity-60"
        >
          {saveStatus === 'saving' ? 'Saving…' : saveStatus === 'saved' ? '✓ Saved' : 'Save'}
        </button>
        <button
          onClick={handleRun}
          disabled={createRun.isPending}
          className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 shadow-sm transition-colors disabled:opacity-60"
        >
          {createRun.isPending ? 'Starting…' : '▶ Run Workflow'}
        </button>
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        onDrop={onDrop}
        onDragOver={onDragOver}
        fitView
        fitViewOptions={{ padding: 0.3 }}
      >
        <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="#e2e8f0" />
        <Controls />
        <MiniMap
          nodeColor={node => MINIMAP_COLORS[(node.data as StepNodeType['data']).type_key] ?? '#94a3b8'}
        />
      </ReactFlow>
    </div>
  )
}

export default function WorkflowBuilder() {
  const { id } = useParams<{ id: string }>()
  const { data: workflow } = useWorkflow(id)
  const { data: registryTypes } = useRegistryTypes('step')

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
        <div className="flex-1 flex items-center justify-center text-slate-400 text-sm">
          Loading workflow…
        </div>
      )}
    </div>
  )
}
