import { useRef, useState } from 'react'
import { toast } from '../store/toast'
import { useCvatModels, useDeployCvatModel, useDeleteCvatModel } from '../api/cvat'
import { Badge, Button, Card, EmptyState, ErrorState, Field, Input, Label, Spinner } from '../components/ui'

export default function CvatModels() {
  const { data: models, isLoading, error } = useCvatModels()
  const deploy = useDeployCvatModel()
  const deleteModel = useDeleteCvatModel()

  const [showForm, setShowForm] = useState(false)
  const [modelName, setModelName] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  async function handleDeploy(e: React.FormEvent) {
    e.preventDefault()
    if (!file) return
    const name = modelName
    const toastId = toast.info(`Deploying "${name}"…`, 'This may take a few minutes', 0)
    try {
      await deploy.mutateAsync({ modelName: name, file })
      toast.dismiss(toastId)
      toast.success(`Model "${name}" deployed successfully`)
      setModelName('')
      setFile(null)
      if (fileRef.current) fileRef.current.value = ''
      setShowForm(false)
    } catch {
      toast.dismiss(toastId)
      toast.error(`Failed to deploy "${name}"`)
    }
  }

  async function handleDelete(id: string, name: string) {
    if (!confirm(`Delete "${name}"?`)) return
    const toastId = toast.info(`Deleting "${name}"…`, undefined, 0)
    try {
      await deleteModel.mutateAsync(id)
      toast.dismiss(toastId)
      toast.success(`Model "${name}" deleted`)
    } catch {
      toast.dismiss(toastId)
      toast.error(`Failed to delete "${name}"`)
    }
  }

  return (
    <div className="mx-auto max-w-5xl p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-text-primary">Deployed Models</h2>
          <p className="mt-0.5 text-sm text-text-muted">Models currently deployed in CVAT via Nuclio</p>
        </div>
        <Button onClick={() => setShowForm((v) => !v)}>+ Deploy Model</Button>
      </div>

      {showForm && (
        <Card className="mb-6 p-4">
          <form onSubmit={handleDeploy} className="flex flex-col gap-3">
            <div className="flex items-end gap-3">
              <Field label="Model name" className="flex-1">
                <Input
                  required
                  autoFocus
                  value={modelName}
                  onChange={(e) => setModelName(e.target.value)}
                  placeholder="e.g. yolov8n"
                />
              </Field>
              <div className="flex-1">
                <Label>Weights file (.pt)</Label>
                <input
                  required
                  ref={fileRef}
                  type="file"
                  accept=".pt"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  className="w-full text-sm text-text-secondary file:mr-3 file:rounded-lg file:border-0 file:bg-iris/10 file:px-3 file:py-2 file:text-sm file:font-medium file:text-iris-400 hover:file:bg-iris/20"
                />
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Button type="submit" loading={deploy.isPending} disabled={!file}>
                {deploy.isPending ? 'Deploying…' : 'Deploy'}
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => setShowForm(false)}
                disabled={deploy.isPending}
              >
                Cancel
              </Button>
              {deploy.isPending && (
                <span className="text-xs text-text-muted">Building Docker image, may take a few minutes…</span>
              )}
            </div>
          </form>
        </Card>
      )}

      {isLoading && (
        <div className="flex items-center justify-center gap-3 py-16 text-sm text-text-muted">
          <Spinner className="h-5 w-5" />
          Loading models…
        </div>
      )}

      {error && <ErrorState description="Failed to load models." />}

      {models && models.length === 0 && (
        <EmptyState
          title="No models deployed"
          description='Click "Deploy Model" to upload a .pt file'
        />
      )}

      {models && models.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {models.map((m) => (
            <Card key={m.id} className="px-5 py-4">
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-semibold text-text-primary">{m.name}</p>
                  <p className="mt-1 font-mono text-xs text-text-muted">{m.id}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone="info" className="capitalize">
                    {m.kind || 'detector'}
                  </Badge>
                  <button
                    onClick={() => handleDelete(m.id, m.name)}
                    disabled={deleteModel.isPending}
                    className="text-text-muted transition-colors hover:text-error disabled:opacity-40"
                    title="Delete model"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
                    </svg>
                  </button>
                </div>
              </div>
              {m.description && <p className="mt-2 text-xs text-text-secondary">{m.description}</p>}
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
