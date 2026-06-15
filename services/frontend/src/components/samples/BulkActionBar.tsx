import { useState } from 'react'
import { useBulkSampleAction } from '../../api/samples'
import { useCollections } from '../../api/collections'
import { useSelectionStore } from '../../store/selection'
import { toast } from '../../store/toast'
import { Button, Dialog, Field, Select } from '../ui'
import { TagPicker } from './TagPicker'
import { AddToDatasetDialog } from './AddToDatasetDialog'

export function BulkActionBar({
  projectId,
  onEdit,
}: {
  projectId: string
  onEdit: (id: string) => void
}) {
  const selected = useSelectionStore((s) => s.selected)
  const clear = useSelectionStore((s) => s.clear)
  const bulk = useBulkSampleAction(projectId)
  const collectionsQuery = useCollections(projectId)
  const collections = collectionsQuery.data?.pages.flatMap((p) => p.items) ?? []

  const [showTag, setShowTag] = useState(false)
  const [showCollection, setShowCollection] = useState(false)
  const [showDelete, setShowDelete] = useState(false)
  const [showDataset, setShowDataset] = useState(false)
  const [tagIds, setTagIds] = useState<string[]>([])
  const [collectionId, setCollectionId] = useState('')

  if (selected.size === 0) return null
  const ids = [...selected]

  async function review(status: 'accepted' | 'rejected') {
    try {
      const res = await bulk.mutateAsync({ action: 'set_review_status', sample_ids: ids, review_status: status })
      toast.success(`Marked ${res.affected} ${status}`)
      clear()
    } catch {
      /* global handler toasts */
    }
  }

  async function applyTags() {
    if (tagIds.length === 0) return
    try {
      await bulk.mutateAsync({ action: 'add_tags', sample_ids: ids, tag_ids: tagIds })
      toast.success(`Tagged ${ids.length} samples`)
      setShowTag(false)
      setTagIds([])
      clear()
    } catch {
      /* global handler toasts */
    }
  }

  async function addToCollection() {
    if (!collectionId) return
    try {
      const res = await bulk.mutateAsync({ action: 'add_to_collection', sample_ids: ids, collection_id: collectionId })
      toast.success(`Added ${res.affected} to collection`)
      setShowCollection(false)
      setCollectionId('')
      clear()
    } catch {
      /* global handler toasts */
    }
  }

  async function remove() {
    try {
      const res = await bulk.mutateAsync({ action: 'delete', sample_ids: ids })
      toast.success(`Deleted ${res.affected} samples`)
      setShowDelete(false)
      clear()
    } catch {
      /* global handler toasts */
    }
  }

  return (
    <>
      <div className="fixed inset-x-0 bottom-4 z-30 flex justify-center px-4">
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-surface-3 px-3 py-2 shadow-lg">
          <span className="px-1 text-sm font-medium text-text-primary">{selected.size} selected</span>
          {selected.size === 1 && (
            <Button size="sm" variant="secondary" onClick={() => onEdit(ids[0])}>
              Edit
            </Button>
          )}
          <Button size="sm" variant="secondary" loading={bulk.isPending} onClick={() => review('accepted')}>
            Accept
          </Button>
          <Button size="sm" variant="secondary" loading={bulk.isPending} onClick={() => review('rejected')}>
            Reject
          </Button>
          <Button size="sm" variant="secondary" onClick={() => setShowTag(true)}>
            Tag
          </Button>
          <Button size="sm" variant="secondary" onClick={() => setShowCollection(true)}>
            Add to collection
          </Button>
          <Button size="sm" onClick={() => setShowDataset(true)}>
            Add to dataset
          </Button>
          <Button size="sm" variant="ghost" className="text-error hover:text-error" onClick={() => setShowDelete(true)}>
            Delete
          </Button>
          <button
            type="button"
            aria-label="Clear selection"
            onClick={clear}
            className="ml-1 rounded p-1 text-text-muted hover:text-text-primary"
          >
            ✕
          </button>
        </div>
      </div>

      <Dialog open={showTag} onClose={() => setShowTag(false)} title={`Tag ${ids.length} samples`}>
        <div className="space-y-4">
          <TagPicker projectId={projectId} value={tagIds} onChange={setTagIds} />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setShowTag(false)}>
              Cancel
            </Button>
            <Button loading={bulk.isPending} disabled={tagIds.length === 0} onClick={applyTags}>
              Apply tags
            </Button>
          </div>
        </div>
      </Dialog>

      <Dialog open={showCollection} onClose={() => setShowCollection(false)} title={`Add ${ids.length} to a collection`}>
        <div className="space-y-4">
          <Field label="Collection" htmlFor="bulk-collection">
            <Select id="bulk-collection" value={collectionId} onChange={(e) => setCollectionId(e.target.value)}>
              <option value="">Select a collection…</option>
              {collections.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          </Field>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setShowCollection(false)}>
              Cancel
            </Button>
            <Button loading={bulk.isPending} disabled={!collectionId} onClick={addToCollection}>
              Add
            </Button>
          </div>
        </div>
      </Dialog>

      <Dialog open={showDelete} onClose={() => setShowDelete(false)} title={`Delete ${ids.length} samples?`}>
        <div className="space-y-4">
          <p className="text-sm text-text-secondary">
            They will be soft-deleted and removed from this list. This cannot be undone from the UI.
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setShowDelete(false)}>
              Cancel
            </Button>
            <Button variant="danger" loading={bulk.isPending} onClick={remove}>
              Delete
            </Button>
          </div>
        </div>
      </Dialog>

      <AddToDatasetDialog
        projectId={projectId}
        sampleIds={ids}
        open={showDataset}
        onClose={() => setShowDataset(false)}
        onDone={clear}
      />
    </>
  )
}
