import { Handle, Position } from '@xyflow/react'
import type { Node, NodeProps } from '@xyflow/react'
import { STEP_META, stepColor, stepLabel } from '../../lib/stepMeta'

export type StepNodeData = {
  label: string
  type_key: string
  status?: string | null
  config?: Record<string, unknown>
}

export type StepNodeType = Node<StepNodeData, 'step'>

const STATUS_RING: Record<string, string> = {
  completed: 'ring-success',
  running: 'ring-warning',
  failed: 'ring-error',
  waiting: 'ring-iris',
}

// One handle per side. Each acts as both connection start and end, so an edge
// can be drawn from — or dropped onto — any side of the node.
const SIDES: { id: string; position: Position }[] = [
  { id: 'top', position: Position.Top },
  { id: 'right', position: Position.Right },
  { id: 'bottom', position: Position.Bottom },
  { id: 'left', position: Position.Left },
]

export function StepNode({ data, selected }: NodeProps<StepNodeType>) {
  const color = stepColor(data.type_key)
  const meta = STEP_META[data.type_key]
  const ring = data.status ? (STATUS_RING[data.status] ?? '') : ''

  return (
    <div
      className={[
        'group relative w-48 select-none overflow-hidden rounded-xl border bg-surface-2 shadow-md transition-shadow',
        selected ? 'border-iris ring-2 ring-iris' : 'border-border hover:shadow-lg',
        ring && !selected ? `ring-2 ${ring}` : '',
      ].join(' ')}
    >
      {SIDES.map((s) => (
        <Handle
          key={s.id}
          id={s.id}
          type="source"
          position={s.position}
          isConnectableStart
          isConnectableEnd
          className="!h-2.5 !w-2.5 !border-2 !border-surface-2 !opacity-40 transition-opacity group-hover:!opacity-100"
          style={{ background: color }}
        />
      ))}

      <div className="flex items-center gap-2 px-3 py-1.5" style={{ background: `${color}1f` }}>
        <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: color }} />
        <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color }}>
          {stepLabel(data.type_key)}
        </span>
        {meta && !meta.runnable && (
          <span className="ml-auto rounded bg-surface-3 px-1 py-0.5 text-[9px] font-medium uppercase text-text-muted">
            stub
          </span>
        )}
      </div>

      <div className="px-3 py-2.5">
        <p className="text-sm font-semibold leading-tight text-text-primary">{data.label}</p>
        {data.status && (
          <span className="mt-0.5 block text-xs capitalize text-text-secondary">{data.status}</span>
        )}
      </div>
    </div>
  )
}
