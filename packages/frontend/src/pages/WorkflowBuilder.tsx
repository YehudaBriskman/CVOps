import { useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
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
import { STEP_TYPES } from '../lib/stepCatalog'

const INITIAL_NODES: StepNodeType[] = [
  { id: 'extract',   type: 'step', position: { x: 50,   y: 150 }, data: { label: 'Extract Frames',  type_key: 'step.extract_frames',  status: null } },
  { id: 'autolabel', type: 'step', position: { x: 290,  y: 150 }, data: { label: 'Auto Label',       type_key: 'step.auto_label',      status: null } },
  { id: 'review',    type: 'step', position: { x: 530,  y: 150 }, data: { label: 'Human Review',     type_key: 'step.human_review',    status: null } },
  { id: 'commit',    type: 'step', position: { x: 770,  y: 150 }, data: { label: 'Commit Dataset',   type_key: 'step.commit_dataset',  status: null } },
  { id: 'export',    type: 'step', position: { x: 1010, y: 150 }, data: { label: 'Export YOLO',      type_key: 'step.export_yolo',     status: null } },
  { id: 'train',     type: 'step', position: { x: 1250, y: 150 }, data: { label: 'Train',            type_key: 'step.train',           status: null } },
]

const INITIAL_EDGES: Edge[] = [
  { id: 'e1', source: 'extract',   target: 'autolabel' },
  { id: 'e2', source: 'autolabel', target: 'review'    },
  { id: 'e3', source: 'review',    target: 'commit'    },
  { id: 'e4', source: 'commit',    target: 'export'    },
  { id: 'e5', source: 'export',    target: 'train'     },
]

const MINIMAP_COLORS: Record<string, string> = {
  'step.extract_frames': '#3b82f6',
  'step.auto_label':     '#a855f7',
  'step.human_review':   '#f97316',
  'step.commit_dataset': '#16a34a',
  'step.export_yolo':    '#eab308',
  'step.train':          '#ef4444',
}

function FlowCanvas() {
  const [nodes, setNodes, onNodesChange] = useNodesState<StepNodeType>(INITIAL_NODES)
  const [edges, setEdges, onEdgesChange] = useEdgesState(INITIAL_EDGES)
  const { screenToFlowPosition } = useReactFlow()
  const navigate = useNavigate()

  const nodeTypes = useMemo(() => ({ step: StepNode }), [])

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
      const stepType = STEP_TYPES.find(s => s.type_key === typeKey)

      setNodes(nds => [
        ...nds,
        {
          id: `${typeKey}-${Date.now()}`,
          type: 'step',
          position,
          data: { label: stepType?.label ?? typeKey, type_key: typeKey, status: null },
        },
      ])
    },
    [screenToFlowPosition, setNodes],
  )

  return (
    <div className="flex-1 relative">
      {/* Toolbar */}
      <div className="absolute top-4 right-4 z-10 flex gap-2">
        <button className="bg-white border border-slate-300 text-slate-700 px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-50 shadow-sm transition-colors">
          Save
        </button>
        <button
          onClick={() => navigate('/runs/run-1')}
          className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 shadow-sm transition-colors"
        >
          ▶ Run Workflow
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
  return (
    <div className="flex" style={{ height: 'calc(100vh - 56px)' }}>
      <StepPalette />
      <ReactFlowProvider>
        <FlowCanvas />
      </ReactFlowProvider>
    </div>
  )
}
