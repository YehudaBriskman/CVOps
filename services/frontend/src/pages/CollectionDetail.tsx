import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  useCollection,
  useCollectionSamples,
  useUpdateCollection,
  useDeleteCollection,
} from '../api/collections'
import {
  Breadcrumbs,
  Button,
  Dialog,
  ErrorState,
  Field,
  Input,
  Textarea,
  SkeletonList,
} from '../components/ui'
import { SampleGrid } from '../components/dataset/SampleGrid'
import { toast } from '../store/toast'

export default function CollectionDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const { data: collection, isLoading, isError, refetch } = useCollection(id)
  const samplesQuery = useCollectionSamples(id)
  const updateCollection = useUpdateCollection(collection?.project_id)
  const deleteCollection = useDeleteCollection(collection?.project_id)

  const [showRename, setShowRename] = useState(false)
  const [showDelete, setShowDelete] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')

  function openRename() {
    if (!collection) return
    setName(collection.name)
    setDescription(collection.description ?? '')
    setShowRename(true)
  }

  async function handleRename(e: React.FormEvent) {
    e.preventDefault()
    if (!id) return
    try {
      await updateCollection.mutateAsync({
        id,
        name,
        description: description.trim() || undefined,
      })
      setShowRename(false)
      toast.success('Collection updated')
    } catch {
      toast.error('Could not update collection')
    }
  }

  async function handleDelete() {
    if (!id || !collection) return
    try {
      await deleteCollection.mutateAsync(id)
      toast.success('Collection deleted')
      navigate(`/projects/${collection.project_id}/collections`)
    } catch {
      toast.error('Could not delete collection')
    }
  }

  if (isLoading) {
    return (
      <div className="mx-auto max-w-5xl p-6">
        <SkeletonList rows={3} />
      </div>
    )
  }

  if (isError || !collection) {
    return (
      <div className="mx-auto max-w-5xl p-6">
        <ErrorState description="Could not load this collection." onRetry={() => refetch()} />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-5xl p-6">
      <Breadcrumbs
        items={[
          { label: 'Collections', to: `/projects/${collection.project_id}/collections` },
          { label: collection.name },
        ]}
      />

      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-text-primary">{collection.name}</h2>
          {collection.description && (
            <p className="mt-0.5 text-sm text-text-muted">{collection.description}</p>
          )}
          {collection.sample_count != null && (
            <p className="mt-0.5 text-xs text-text-muted">
              {collection.sample_count} {collection.sample_count === 1 ? 'sample' : 'samples'}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={openRename}>
            Rename
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="text-error hover:text-error"
            onClick={() => setShowDelete(true)}
          >
            Delete
          </Button>
        </div>
      </div>

      <Dialog open={showRename} onClose={() => setShowRename(false)} title="Rename collection">
        <form onSubmit={handleRename} className="space-y-4">
          <Field label="Name" htmlFor="collection-rename">
            <Input
              id="collection-rename"
              required
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Collection name"
            />
          </Field>
          <Field label="Description" htmlFor="collection-rename-description">
            <Textarea
              id="collection-rename-description"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
            />
          </Field>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={() => setShowRename(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={updateCollection.isPending}>
              Save
            </Button>
          </div>
        </form>
      </Dialog>

      <Dialog open={showDelete} onClose={() => setShowDelete(false)} title="Delete collection">
        <p className="text-sm text-text-secondary">
          Delete <span className="font-semibold text-text-primary">{collection.name}</span>? This
          removes the collection but not its samples.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={() => setShowDelete(false)}>
            Cancel
          </Button>
          <Button
            variant="ghost"
            className="text-error hover:text-error"
            loading={deleteCollection.isPending}
            onClick={handleDelete}
          >
            Delete
          </Button>
        </div>
      </Dialog>

      <SampleGrid
        data={samplesQuery.data}
        isLoading={samplesQuery.isLoading}
        hasNextPage={samplesQuery.hasNextPage}
        isFetchingNextPage={samplesQuery.isFetchingNextPage}
        fetchNextPage={samplesQuery.fetchNextPage}
      />
    </div>
  )
}
