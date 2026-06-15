import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  useCollections,
  useCreateCollection,
  type Collection,
} from '../api/collections'
import {
  Breadcrumbs,
  Button,
  Card,
  Dialog,
  EmptyState,
  ErrorState,
  Field,
  Input,
  Textarea,
  SkeletonList,
} from '../components/ui'
import { toast } from '../store/toast'

export default function Collections() {
  const { id: projectId } = useParams<{ id: string }>()
  const { data, isLoading, isError, refetch } = useCollections(projectId)
  const createCollection = useCreateCollection(projectId)

  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')

  const collections: Collection[] = data?.pages.flatMap((p) => p.items) ?? []

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    try {
      await createCollection.mutateAsync({
        name,
        description: description.trim() || undefined,
      })
      setName('')
      setDescription('')
      setShowForm(false)
      toast.success('Collection created')
    } catch {
      toast.error('Could not create collection')
    }
  }

  return (
    <div className="mx-auto max-w-5xl p-6">
      <Breadcrumbs
        items={[{ label: 'Project', to: `/projects/${projectId}` }, { label: 'Collections' }]}
      />

      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-xl font-bold text-text-primary">Collections</h2>
        <Button onClick={() => setShowForm(true)}>+ New Collection</Button>
      </div>

      <Dialog open={showForm} onClose={() => setShowForm(false)} title="New collection">
        <form onSubmit={handleCreate} className="space-y-4">
          <Field label="Name" htmlFor="collection-name">
            <Input
              id="collection-name"
              required
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My collection"
            />
          </Field>
          <Field label="Description" htmlFor="collection-description">
            <Textarea
              id="collection-description"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
            />
          </Field>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={() => setShowForm(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={createCollection.isPending}>
              Create
            </Button>
          </div>
        </form>
      </Dialog>

      {isLoading && <SkeletonList rows={3} />}

      {isError && (
        <ErrorState
          description="Could not load collections for this project."
          onRetry={() => refetch()}
        />
      )}

      {data && collections.length === 0 && (
        <EmptyState
          title="No collections yet"
          description="Group samples into collections to organise your data."
          action={<Button onClick={() => setShowForm(true)}>+ New Collection</Button>}
        />
      )}

      {collections.length > 0 && (
        <div className="space-y-2">
          {collections.map((c) => (
            <Link key={c.id} to={`/collections/${c.id}`}>
              <Card className="flex items-center justify-between px-5 py-4 transition-all hover:border-iris hover:shadow-md">
                <div>
                  <p className="font-semibold text-text-primary">{c.name}</p>
                  {c.description && (
                    <p className="mt-0.5 text-xs text-text-muted">{c.description}</p>
                  )}
                  {c.sample_count != null && (
                    <p className="mt-0.5 text-xs text-text-muted">
                      {c.sample_count} {c.sample_count === 1 ? 'sample' : 'samples'}
                    </p>
                  )}
                </div>
                <span className="text-lg text-text-muted">›</span>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
