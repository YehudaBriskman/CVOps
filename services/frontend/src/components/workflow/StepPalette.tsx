import type { StepTypeDef } from '../../lib/stepCatalog'

interface Props {
  steps?: StepTypeDef[]
}

export function StepPalette({ steps }: Props) {
  const onDragStart = (e: React.DragEvent, typeKey: string) => {
    e.dataTransfer.setData('application/xyflow', typeKey)
    e.dataTransfer.effectAllowed = 'move'
  }

  const items = steps ?? []

  return (
    <div className="w-56 bg-white border-r border-slate-200 flex flex-col flex-shrink-0 overflow-y-auto">
      <div className="px-4 py-3 border-b border-slate-100 flex-shrink-0">
        <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">Steps</p>
        <p className="text-xs text-slate-400 mt-0.5">Drag onto canvas</p>
      </div>

      <div className="p-3 space-y-2">
        {items.map(step => (
          <div
            key={step.type_key}
            draggable
            onDragStart={e => onDragStart(e, step.type_key)}
            className="rounded-lg border border-slate-200 bg-white shadow-sm p-3 cursor-grab active:cursor-grabbing hover:border-indigo-300 hover:shadow-md transition-all"
          >
            <div className="flex items-center gap-2 mb-1">
              <div className={`w-2 h-2 rounded-full flex-shrink-0 ${step.accent}`} />
              <span className="text-xs font-semibold text-slate-700">{step.label}</span>
            </div>
            <p className="text-xs text-slate-400 leading-snug">{step.description}</p>
          </div>
        ))}

        {items.length === 0 && (
          <p className="text-xs text-slate-400 px-1">No steps registered</p>
        )}
      </div>
    </div>
  )
}
