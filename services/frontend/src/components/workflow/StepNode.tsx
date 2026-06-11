import { Handle, Position } from '@xyflow/react'
import type { Node, NodeProps } from '@xyflow/react'

export type StepNodeData = {
  label: string
  type_key: string
  status?: string | null
}

export type StepNodeType = Node<StepNodeData, 'step'>

const ACCENT: Record<string, string> = {
  'step.extract_frames':  'bg-blue-500',
  'step.auto_label':      'bg-purple-500',
  'step.human_review':    'bg-orange-500',
  'step.commit_dataset':  'bg-green-600',
  'step.export_yolo':     'bg-yellow-500',
  'step.train':           'bg-red-500',
}

const STATUS_BORDER: Record<string, string> = {
  completed: 'border-green-400',
  running:   'border-amber-400',
  failed:    'border-red-400',
}

export function StepNode({ data }: NodeProps<StepNodeType>) {
  const accent = ACCENT[data.type_key] ?? 'bg-slate-500'
  const border = STATUS_BORDER[data.status ?? ''] ?? 'border-slate-200'

  return (
    <div className={`rounded-xl border-2 ${border} bg-white shadow-md w-44 overflow-hidden select-none`}>
      <Handle type="target" position={Position.Left}  className="!w-3 !h-3 !bg-slate-300 !border-white" />
      <div className={`${accent} px-3 py-1.5`}>
        <span className="text-white text-[10px] font-bold tracking-widest uppercase">
          {data.type_key.replace('step.', '')}
        </span>
      </div>
      <div className="px-3 py-2.5">
        <p className="text-sm font-semibold text-slate-800 leading-tight">{data.label}</p>
        {data.status && (
          <span className="text-xs text-slate-500 capitalize mt-0.5 block">{data.status}</span>
        )}
      </div>
      <Handle type="source" position={Position.Right} className="!w-3 !h-3 !bg-slate-300 !border-white" />
    </div>
  )
}
