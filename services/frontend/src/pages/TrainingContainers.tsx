import { useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  useTrainingContainers,
  useCreateTrainingContainer,
  useUpdateTrainingContainer,
  useDeleteTrainingContainer,
  type TrainingContainer,
} from '../api/training-containers'
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

const ICD_PLACEHOLDER = `{
  "inputs": {
    "epochs": { "env": "EPOCHS", "type": "integer", "default": 50 }
  }
}`

interface FormState {
  name: string
  description: string
  image: string
  icdConfigText: string
}

const EMPTY_FORM: FormState = { name: '', description: '', image: '', icdConfigText: '' }

function toForm(tc: TrainingContainer): FormState {
  return {
    name: tc.name,
    description: tc.description ?? '',
    image: tc.image,
    icdConfigText: tc.icd_config ? JSON.stringify(tc.icd_config, null, 2) : '',
  }
}

export default function TrainingContainers() {
  const { id: projectId } = useParams<{ id: string }>()
  const { data: containers, isLoading, isError, refetch } = useTrainingContainers(projectId)

  // `null` = closed; a TrainingContainer = editing that one; 'new' = creating.
  const [editing, setEditing] = useState<TrainingContainer | 'new' | null>(null)

  const deleteContainer = useDeleteTrainingContainer(projectId)

  function handleDelete(tc: TrainingContainer) {
    if (!window.confirm(`Delete training environment "${tc.name}"?`)) return
    deleteContainer.mutate(tc.id, {
      onSuccess: () => toast.success('Training environment deleted'),
    })
  }

  return (
    <div className="mx-auto max-w-5xl p-6">
      <Breadcrumbs
        items={[{ label: 'Project', to: `/projects/${projectId}` }, { label: 'Training' }]}
      />

      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-text-primary">Training Environments</h2>
          <p className="mt-0.5 text-sm text-text-muted">
            Reusable Docker image + ICD config consumed by the train step
          </p>
        </div>
        <Button onClick={() => setEditing('new')}>+ New Environment</Button>
      </div>

      {isLoading && <SkeletonList rows={3} />}

      {isError && (
        <ErrorState
          description="Could not load training environments for this project."
          onRetry={() => refetch()}
        />
      )}

      {containers && containers.length === 0 && (
        <EmptyState
          title="No training environments yet"
          description="Create one to make a saved image + ICD reusable from the Train modal."
          action={<Button onClick={() => setEditing('new')}>+ New Environment</Button>}
        />
      )}

      {containers && containers.length > 0 && (
        <div className="space-y-2">
          {containers.map((tc) => (
            <Card key={tc.id} className="flex items-center justify-between px-5 py-4">
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-text-primary">{tc.name}</p>
                <p className="mt-0.5 truncate font-mono text-xs text-text-muted">{tc.image}</p>
                {tc.description && (
                  <p className="mt-0.5 truncate text-xs text-text-secondary">{tc.description}</p>
                )}
              </div>
              <div className="ml-3 flex items-center gap-2">
                <Button variant="secondary" size="sm" onClick={() => setEditing(tc)}>
                  Edit
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-error hover:text-error"
                  loading={deleteContainer.isPending && deleteContainer.variables === tc.id}
                  onClick={() => handleDelete(tc)}
                >
                  Delete
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {editing !== null && (
        <ContainerDialog
          projectId={projectId}
          container={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  )
}

function ContainerDialog({
  projectId,
  container,
  onClose,
}: {
  projectId: string | undefined
  container: TrainingContainer | null
  onClose: () => void
}) {
  const [form, setForm] = useState<FormState>(container ? toForm(container) : EMPTY_FORM)
  const [icdError, setIcdError] = useState<string | undefined>()

  const create = useCreateTrainingContainer(projectId)
  const update = useUpdateTrainingContainer(container?.id ?? '', projectId)
  const pending = create.isPending || update.isPending

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()

    let icd_config: Record<string, unknown>
    const text = form.icdConfigText.trim()
    try {
      icd_config = text ? JSON.parse(text) : {}
    } catch (err) {
      setIcdError(err instanceof Error ? err.message : 'Invalid JSON')
      return
    }
    if (typeof icd_config !== 'object' || icd_config === null || Array.isArray(icd_config)) {
      setIcdError('icd_config must be a JSON object')
      return
    }
    setIcdError(undefined)

    const body = {
      name: form.name,
      description: form.description || null,
      image: form.image,
      icd_config,
    }

    if (container) {
      await update.mutateAsync(body)
      toast.success('Training environment updated')
    } else {
      await create.mutateAsync(body)
      toast.success('Training environment created')
    }
    onClose()
  }

  return (
    <Dialog
      open
      onClose={onClose}
      title={container ? 'Edit training environment' : 'New training environment'}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <Field label="Name" htmlFor="tc-name">
          <Input
            id="tc-name"
            required
            autoFocus
            value={form.name}
            onChange={(e) => set('name', e.target.value)}
            placeholder="yolo-trainer"
          />
        </Field>
        <Field label="Description" htmlFor="tc-description">
          <Input
            id="tc-description"
            value={form.description}
            onChange={(e) => set('description', e.target.value)}
            placeholder="Optional"
          />
        </Field>
        <Field label="Image" htmlFor="tc-image">
          <Input
            id="tc-image"
            required
            value={form.image}
            onChange={(e) => set('image', e.target.value)}
            placeholder="ghcr.io/org/trainer:latest"
            className="font-mono"
          />
        </Field>
        <Field label="ICD config (JSON)" htmlFor="tc-icd" error={icdError}>
          <Textarea
            id="tc-icd"
            rows={10}
            value={form.icdConfigText}
            onChange={(e) => set('icdConfigText', e.target.value)}
            placeholder={ICD_PLACEHOLDER}
            className="font-mono text-xs"
          />
        </Field>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={pending}>
            {container ? 'Save' : 'Create'}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
