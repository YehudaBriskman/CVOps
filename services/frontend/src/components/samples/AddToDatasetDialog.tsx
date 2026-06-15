import { useState } from 'react'
import { useDatasets, useCreateDataset, useCommitFromSamples } from '../../api/datasets'
import { toast } from '../../store/toast'
import { Button, Dialog, Field, Input, Select } from '../ui'

export function AddToDatasetDialog({
  projectId,
  sampleIds,
  open,
  onClose,
  onDone,
}: {
  projectId: string
  sampleIds: string[]
  open: boolean
  onClose: () => void
  onDone: () => void
}) {
  const { data: datasets } = useDatasets(projectId)
  const createDataset = useCreateDataset()
  const commit = useCommitFromSamples()

  const [mode, setMode] = useState<'existing' | 'new'>('existing')
  const [datasetId, setDatasetId] = useState('')
  const [newName, setNewName] = useState('')
  const [branch, setBranch] = useState('main')

  const busy = createDataset.isPending || commit.isPending

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    try {
      let dsId = datasetId
      if (mode === 'new') {
        const ds = await createDataset.mutateAsync({ projectId, name: newName })
        dsId = ds.id
      }
      if (!dsId) return
      const res = await commit.mutateAsync({
        datasetId: dsId,
        sample_ids: sampleIds,
        branch_name: branch || 'main',
        message: `Add ${sampleIds.length} samples`,
      })
      toast.success(
        'Added to dataset',
        `${res.committed_count} committed${res.skipped_count ? `, ${res.skipped_count} skipped (unannotated)` : ''}`,
      )
      onDone()
      onClose()
    } catch {
      // Surfaced by the global mutation error handler.
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title={`Add ${sampleIds.length} samples to a dataset`}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="flex gap-2 text-sm">
          <label className="flex items-center gap-1.5 text-text-secondary">
            <input type="radio" checked={mode === 'existing'} onChange={() => setMode('existing')} />
            Existing
          </label>
          <label className="flex items-center gap-1.5 text-text-secondary">
            <input type="radio" checked={mode === 'new'} onChange={() => setMode('new')} />
            New
          </label>
        </div>

        {mode === 'existing' ? (
          <Field label="Dataset" htmlFor="ds-select">
            <Select id="ds-select" value={datasetId} onChange={(e) => setDatasetId(e.target.value)} required>
              <option value="">Select a dataset…</option>
              {datasets?.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </Select>
          </Field>
        ) : (
          <Field label="New dataset name" htmlFor="ds-name">
            <Input id="ds-name" value={newName} onChange={(e) => setNewName(e.target.value)} required placeholder="my-dataset" />
          </Field>
        )}

        <Field label="Branch" htmlFor="ds-branch">
          <Input id="ds-branch" value={branch} onChange={(e) => setBranch(e.target.value)} />
        </Field>

        <p className="text-xs text-text-muted">
          Only annotated samples are committed; unannotated ones are skipped and reported.
        </p>

        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={busy}>
            Add to dataset
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
