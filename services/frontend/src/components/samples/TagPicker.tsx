import { useState } from 'react'
import { useCreateTag, useTags } from '../../api/tags'
import { cn } from '../../lib/cn'
import { Input } from '../ui'

/**
 * Multi-select tag chips with inline create. `value` is the set of selected tag
 * ids; `onChange` is called with the new id list.
 */
export function TagPicker({
  projectId,
  value,
  onChange,
}: {
  projectId: string
  value: string[]
  onChange: (ids: string[]) => void
}) {
  const { data: tags } = useTags(projectId)
  const createTag = useCreateTag(projectId)
  const [newName, setNewName] = useState('')

  function toggle(id: string) {
    onChange(value.includes(id) ? value.filter((t) => t !== id) : [...value, id])
  }

  async function handleCreate() {
    const name = newName.trim()
    if (!name) return
    const tag = await createTag.mutateAsync({ name })
    setNewName('')
    onChange([...value, tag.id])
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {tags?.length === 0 && <p className="text-xs text-text-muted">No tags yet — create one below.</p>}
        {tags?.map((t) => {
          const active = value.includes(t.id)
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => toggle(t.id)}
              className={cn(
                'inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs',
                active
                  ? 'border-iris bg-iris/15 text-text-primary'
                  : 'border-border text-text-secondary hover:bg-surface-3',
              )}
            >
              <span className="h-2 w-2 rounded-full" style={{ backgroundColor: t.color }} />
              {t.name}
            </button>
          )
        })}
      </div>
      <div className="flex gap-2">
        <Input
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              void handleCreate()
            }
          }}
          placeholder="New tag name…"
          className="text-xs"
        />
      </div>
    </div>
  )
}
