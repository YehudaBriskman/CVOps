import { useEffect, useRef, useState } from 'react'
import type { Sample } from '../../api/samples'
import { useBulkSampleAction, useDeleteSample } from '../../api/samples'
import { useCollections, useCreateCollection } from '../../api/collections'
import { toast } from '../../store/toast'
import { cn } from '../../lib/cn'
import { Button, Dialog, Field, Input, Select } from '../ui'
import { TagPicker } from './TagPicker'
import { AddToDatasetDialog } from './AddToDatasetDialog'

/**
 * Per-image kebab (⋮) menu. Every action targets this single sample. The menu
 * panel is a lightweight absolute-positioned dropdown (no external dependency)
 * that closes on click-outside and Escape.
 */
export function SampleImageMenu({
  sample,
  projectId,
  onEdit,
}: {
  sample: Sample
  projectId: string
  onEdit: (s: Sample) => void
}) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  const bulk = useBulkSampleAction(projectId)
  const deleteSample = useDeleteSample(projectId)
  const collectionsQuery = useCollections(projectId)
  const createCollection = useCreateCollection(projectId)
  const collections = collectionsQuery.data?.pages.flatMap((p) => p.items) ?? []

  const [showTag, setShowTag] = useState(false)
  const [showCollection, setShowCollection] = useState(false)
  const [showDataset, setShowDataset] = useState(false)
  const [showDelete, setShowDelete] = useState(false)
  const [tagIds, setTagIds] = useState<string[]>([])
  const [collectionMode, setCollectionMode] = useState<'existing' | 'new'>('existing')
  const [collectionId, setCollectionId] = useState('')
  const [newCollectionName, setNewCollectionName] = useState('')

  useEffect(() => {
    if (!open) return
    function onPointer(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  async function review(status: 'accepted' | 'rejected') {
    setOpen(false)
    try {
      await bulk.mutateAsync({ action: 'set_review_status', sample_ids: [sample.id], review_status: status })
      toast.success(`Marked ${status}`)
    } catch {
      /* global handler toasts */
    }
  }

  async function applyTags() {
    if (tagIds.length === 0) return
    try {
      await bulk.mutateAsync({ action: 'add_tags', sample_ids: [sample.id], tag_ids: tagIds })
      toast.success('Tags added')
      setShowTag(false)
      setTagIds([])
    } catch {
      /* global handler toasts */
    }
  }

  async function addToCollection() {
    try {
      let targetId = collectionId
      if (collectionMode === 'new') {
        const name = newCollectionName.trim()
        if (!name) return
        const created = await createCollection.mutateAsync({ name })
        targetId = created.id
      }
      if (!targetId) return
      await bulk.mutateAsync({ action: 'add_to_collection', sample_ids: [sample.id], collection_id: targetId })
      toast.success('Added to collection')
      setShowCollection(false)
      setCollectionId('')
      setNewCollectionName('')
      setCollectionMode('existing')
    } catch {
      /* global handler toasts */
    }
  }

  async function remove() {
    try {
      await deleteSample.mutateAsync(sample.id)
      toast.success('Sample deleted')
      setShowDelete(false)
    } catch {
      /* global handler toasts */
    }
  }

  const itemClass =
    'flex w-full items-center px-3 py-1.5 text-left text-xs text-text-primary hover:bg-surface-2'

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        aria-label="Sample actions"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'flex h-5 w-5 items-center justify-center rounded border text-xs leading-none transition-opacity',
          open
            ? 'border-white/70 bg-black/60 text-white opacity-100'
            : 'border-white/70 bg-black/40 text-white opacity-0 group-hover:opacity-100 focus:opacity-100',
        )}
      >
        ⋮
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-6 z-20 w-40 overflow-hidden rounded-lg border border-border bg-surface-3 py-1 text-text-primary shadow-lg"
        >
          <button type="button" role="menuitem" className={itemClass} onClick={() => review('accepted')}>
            Accept
          </button>
          <button type="button" role="menuitem" className={itemClass} onClick={() => review('rejected')}>
            Reject
          </button>
          <button
            type="button"
            role="menuitem"
            className={itemClass}
            onClick={() => {
              setOpen(false)
              setShowTag(true)
            }}
          >
            Add tags
          </button>
          <button
            type="button"
            role="menuitem"
            className={itemClass}
            onClick={() => {
              setOpen(false)
              setShowCollection(true)
            }}
          >
            Add to collection
          </button>
          <button
            type="button"
            role="menuitem"
            className={itemClass}
            onClick={() => {
              setOpen(false)
              setShowDataset(true)
            }}
          >
            Add to dataset
          </button>
          <button
            type="button"
            role="menuitem"
            className={itemClass}
            onClick={() => {
              setOpen(false)
              onEdit(sample)
            }}
          >
            Edit
          </button>
          <button
            type="button"
            role="menuitem"
            className={cn(itemClass, 'text-error hover:text-error')}
            onClick={() => {
              setOpen(false)
              setShowDelete(true)
            }}
          >
            Delete
          </button>
        </div>
      )}

      <Dialog open={showTag} onClose={() => setShowTag(false)} title="Add tags">
        <div className="space-y-4">
          <TagPicker projectId={projectId} value={tagIds} onChange={setTagIds} />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setShowTag(false)}>
              Cancel
            </Button>
            <Button loading={bulk.isPending} disabled={tagIds.length === 0} onClick={applyTags}>
              Add tags
            </Button>
          </div>
        </div>
      </Dialog>

      <Dialog open={showCollection} onClose={() => setShowCollection(false)} title="Add to a collection">
        <div className="space-y-4">
          <div className="flex gap-2 text-sm">
            <label className="flex items-center gap-1.5 text-text-secondary">
              <input
                type="radio"
                checked={collectionMode === 'existing'}
                onChange={() => setCollectionMode('existing')}
              />
              Existing
            </label>
            <label className="flex items-center gap-1.5 text-text-secondary">
              <input type="radio" checked={collectionMode === 'new'} onChange={() => setCollectionMode('new')} />
              New
            </label>
          </div>

          {collectionMode === 'existing' ? (
            <Field label="Collection" htmlFor="menu-collection">
              <Select id="menu-collection" value={collectionId} onChange={(e) => setCollectionId(e.target.value)}>
                <option value="">Select a collection…</option>
                {collections.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </Select>
            </Field>
          ) : (
            <Field label="New collection name" htmlFor="menu-collection-name">
              <Input
                id="menu-collection-name"
                value={newCollectionName}
                onChange={(e) => setNewCollectionName(e.target.value)}
                placeholder="my-collection"
              />
            </Field>
          )}

          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setShowCollection(false)}>
              Cancel
            </Button>
            <Button
              loading={bulk.isPending || createCollection.isPending}
              disabled={collectionMode === 'existing' ? !collectionId : !newCollectionName.trim()}
              onClick={addToCollection}
            >
              Add
            </Button>
          </div>
        </div>
      </Dialog>

      <Dialog open={showDelete} onClose={() => setShowDelete(false)} title="Delete this sample?">
        <div className="space-y-4">
          <p className="text-sm text-text-secondary">
            It will be soft-deleted and removed from this list. This cannot be undone from the UI.
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setShowDelete(false)}>
              Cancel
            </Button>
            <Button variant="danger" loading={deleteSample.isPending} onClick={remove}>
              Delete
            </Button>
          </div>
        </div>
      </Dialog>

      <AddToDatasetDialog
        projectId={projectId}
        sampleIds={[sample.id]}
        open={showDataset}
        onClose={() => setShowDataset(false)}
        onDone={() => setShowDataset(false)}
      />
    </div>
  )
}
