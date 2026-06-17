import { useEffect, useState } from 'react'
import type { Sample } from '../../api/samples'
import { useDeleteSample, usePatchSample } from '../../api/samples'
import { toast } from '../../store/toast'
import { useSelectionStore } from '../../store/selection'
import { Button, Drawer, Input, Label } from '../ui'
import { TagPicker } from './TagPicker'

interface Row {
  key: string
  value: string
}

function toRows(metadata: Record<string, unknown> | null): Row[] {
  if (!metadata) return []
  return Object.entries(metadata).map(([key, v]) => ({
    key,
    value: typeof v === 'string' ? v : JSON.stringify(v),
  }))
}

export function SampleEditDrawer({
  projectId,
  sample,
  onClose,
}: {
  projectId: string
  sample: Sample | null
  onClose: () => void
}) {
  const patch = usePatchSample(projectId)
  const del = useDeleteSample(projectId)
  const clear = useSelectionStore((s) => s.clear)

  const [rows, setRows] = useState<Row[]>([])
  const [tagIds, setTagIds] = useState<string[]>([])

  useEffect(() => {
    if (sample) {
      setRows(toRows(sample.metadata))
      setTagIds(sample.tags.map((t) => t.id))
    }
  }, [sample])

  async function handleSave() {
    if (!sample) return
    const metadata: Record<string, unknown> = {}
    for (const r of rows) {
      if (r.key.trim()) metadata[r.key.trim()] = r.value
    }
    try {
      await patch.mutateAsync({
        id: sample.id,
        body: { metadata, metadata_mode: 'replace', tag_ids: tagIds },
      })
      toast.success('Sample updated')
      onClose()
    } catch {
      /* errors surface via the global toast handler */
    }
  }

  async function handleDelete() {
    if (!sample) return
    try {
      await del.mutateAsync(sample.id)
      toast.success('Sample deleted')
      clear()
      onClose()
    } catch {
      /* errors surface via the global toast handler */
    }
  }

  return (
    <Drawer open={sample !== null} onClose={onClose} title="Edit sample">
      {sample && (
        <div className="space-y-5">
          <p className="font-mono text-xs text-text-muted">{sample.id}</p>

          <div>
            <Label>Tags</Label>
            <TagPicker projectId={projectId} value={tagIds} onChange={setTagIds} />
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between">
              <Label>Metadata</Label>
              <button
                type="button"
                onClick={() => setRows((r) => [...r, { key: '', value: '' }])}
                className="text-xs text-iris-400 hover:opacity-80"
              >
                + Add field
              </button>
            </div>
            <div className="space-y-2">
              {rows.length === 0 && <p className="text-xs text-text-muted">No metadata.</p>}
              {rows.map((row, i) => (
                <div key={i} className="flex gap-2">
                  <Input
                    placeholder="key"
                    value={row.key}
                    onChange={(e) =>
                      setRows((rs) => rs.map((r, j) => (j === i ? { ...r, key: e.target.value } : r)))
                    }
                    className="w-1/3"
                  />
                  <Input
                    placeholder="value"
                    value={row.value}
                    onChange={(e) =>
                      setRows((rs) => rs.map((r, j) => (j === i ? { ...r, value: e.target.value } : r)))
                    }
                  />
                  <button
                    type="button"
                    aria-label="Remove field"
                    onClick={() => setRows((rs) => rs.filter((_, j) => j !== i))}
                    className="rounded px-2 text-text-muted hover:text-error"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between border-t border-border pt-4">
            <Button variant="ghost" size="sm" className="text-error hover:text-error" loading={del.isPending} onClick={handleDelete}>
              Delete sample
            </Button>
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" onClick={onClose}>
                Cancel
              </Button>
              <Button size="sm" loading={patch.isPending} onClick={handleSave}>
                Save
              </Button>
            </div>
          </div>
        </div>
      )}
    </Drawer>
  )
}
