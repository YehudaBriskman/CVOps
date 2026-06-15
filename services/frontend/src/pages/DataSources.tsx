import { useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { client } from '../lib/client'
import { sha256Hex } from '../lib/hash'
import { putWithProgress } from '../lib/upload'
import { INGEST_WORKFLOW_DEFINITION, INGEST_WORKFLOW_NAME } from '../lib/ingest'
import { useProject } from '../api/projects'
import { useWorkflows, useCreateWorkflow } from '../api/workflows'
import {
  type DataSource,
  type DataSourceMatch,
  type UploadResponse,
  checkDuplicate,
  useDataSourceUrl,
  useDataSources,
  useDeleteDataSource,
} from '../api/data-sources'

function StatusBadge({ ds }: { ds: DataSource }) {
  let label: string
  let cls: string
  let spinner = false

  switch (ds.status) {
    case 'failed':
      label = 'Failed'
      cls = 'bg-error/10 text-error'
      break
    case 'pending':
      label = 'Uploading'
      cls = 'bg-warning/10 text-warning'
      break
    case 'uploaded':
      if (ds.type === 'image') {
        label = 'Ready'
        cls = 'bg-success/10 text-success'
      } else {
        label = 'Queued'
        cls = 'bg-surface-3 text-text-secondary'
        spinner = true
      }
      break
    case 'ingesting':
      label = 'Extracting frames'
      cls = 'bg-iris/10 text-iris-400'
      spinner = true
      break
    case 'ingested':
      label = 'Ready'
      cls = 'bg-success/10 text-success'
      break
    default:
      label = ds.status
      cls = 'bg-surface-3 text-text-secondary'
  }

  return (
    <span className={`inline-flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full font-medium ${cls}`}>
      {spinner && <span className="w-3 h-3 border-2 border-iris-400 border-t-iris rounded-full animate-spin" />}
      {label}
    </span>
  )
}

function SourcePreview({ ds }: { ds: DataSource }) {
  const { data, isLoading, isError } = useDataSourceUrl(ds.id, ds.blob_hash != null)

  if (ds.external_uri && !ds.blob_hash) {
    return (
      <div className="aspect-video bg-surface-1 flex items-center justify-center px-4">
        <a href={ds.external_uri} target="_blank" rel="noreferrer" className="text-xs text-iris-400 hover:underline break-all text-center">
          {ds.external_uri}
        </a>
      </div>
    )
  }

  if (ds.blob_hash == null) {
    return <div className="aspect-video bg-surface-3" />
  }

  if (isLoading) {
    return (
      <div className="aspect-video bg-surface-3 flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-border-strong border-t-text-secondary rounded-full animate-spin" />
      </div>
    )
  }

  if (isError || !data?.url) {
    return (
      <div className="aspect-video bg-surface-1 flex items-center justify-center text-xs text-text-muted">
        Preview unavailable
      </div>
    )
  }

  if (ds.type === 'image') {
    return (
      <div className="aspect-video bg-slate-900">
        <img src={data.url} alt="source" className="w-full h-full object-contain" loading="lazy" />
      </div>
    )
  }

  return (
    <div className="aspect-video bg-black">
      <video src={data.url} controls preload="metadata" className="w-full h-full object-contain" />
    </div>
  )
}

function SourceCard({ ds, projectId, onDelete }: { ds: DataSource; projectId: string; onDelete: (id: string) => void }) {
  const frames = ds.sample_count ?? 0
  return (
    <div className="bg-surface-2 rounded-xl border border-border shadow-sm overflow-hidden flex flex-col">
      <SourcePreview ds={ds} />
      <div className="p-4 flex flex-col gap-3 flex-1">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-sm font-medium text-text-primary capitalize">{ds.type.replace('_', ' ')}</p>
            <p className="text-xs text-text-muted mt-0.5 font-mono">{ds.id.slice(0, 8)}…</p>
          </div>
          <StatusBadge ds={ds} />
        </div>

        <div className="flex items-center justify-between mt-auto">
          {frames > 0 ? (
            <Link
              to={`/projects/${projectId}/samples?source=${ds.id}`}
              className="text-xs font-medium text-iris-400 hover:text-iris-400"
            >
              View {frames} frame{frames === 1 ? '' : 's'} →
            </Link>
          ) : (
            <span className="text-xs text-text-muted">No frames yet</span>
          )}
          <div className="flex items-center gap-3">
            {ds.latest_run_id && (
              <Link
                to={`/runs/${ds.latest_run_id}`}
                className="text-xs font-medium text-iris-400 hover:text-iris-400"
              >
                View run →
              </Link>
            )}
            <button
              onClick={() => onDelete(ds.id)}
              className="text-xs text-error hover:text-error transition-colors"
            >
              Delete
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function DataSources() {
  const { id: projectId } = useParams<{ id: string }>()
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState<string | null>(null)
  // Upload fraction [0,1] during the direct-to-storage PUT, or null for the
  // surrounding indeterminate phases (create / hash / confirm).
  const [pct, setPct] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  // Set when a pre-upload check finds the same content already in the org. The
  // auto-flow pauses on a small modal asking to add-without-reuploading or skip.
  const [dupPrompt, setDupPrompt] = useState<{
    file: File
    blobHash: string
    matches: DataSourceMatch[]
    inCurrentProject: boolean
  } | null>(null)

  const { data: sources, isLoading } = useDataSources(projectId)
  const { data: project } = useProject(projectId)
  const { data: workflows } = useWorkflows(projectId)
  const deleteMutation = useDeleteDataSource(projectId)
  const createWorkflow = useCreateWorkflow()

  // Which workflow to run on the next upload. null = uninitialised; once the
  // project loads we preselect its default ingest workflow (empty string means
  // "just store, no processing"). The dropdown surfaces this choice instead of
  // hiding it behind a project setting.
  const [selectedWf, setSelectedWf] = useState<string | null>(null)
  if (selectedWf === null && project) {
    setSelectedWf(project.default_ingest_workflow_id ?? '')
  }
  const wfValue = selectedWf ?? ''

  async function handleCreateIngestWorkflow() {
    if (!projectId) return
    const wf = await createWorkflow.mutateAsync({
      projectId,
      name: INGEST_WORKFLOW_NAME,
      definition: INGEST_WORKFLOW_DEFINITION,
    })
    setSelectedWf(wf.id)
  }

  // Full path for genuinely new content: create source, PUT the bytes, confirm.
  async function doFreshUpload(file: File, blobHash: string) {
    const type = file.type.startsWith('image/') ? 'image' : 'video'
    setProgress('Creating data source…')
    const { data: upload } = await client.post<UploadResponse>(
      `/projects/${projectId}/data-sources`,
      { type },
    )

    if (upload.presigned_put_url) {
      setProgress('Uploading to storage…')
      setPct(0)
      await putWithProgress(upload.presigned_put_url, file, setPct)
    }

    setPct(null)
    setProgress('Confirming upload…')
    await client.post(`/data-sources/${upload.data_source.id}/confirm-upload`, {
      blob_hash: blobHash,
      // Empty string → omit, so the backend treats it as "no workflow".
      workflow_id: wfValue || undefined,
    })
  }

  // "Add without re-uploading": the bytes already exist in the org, so create
  // the source and confirm against the known hash — no PUT, instant.
  async function doRegisterExisting(file: File, blobHash: string) {
    const type = file.type.startsWith('image/') ? 'image' : 'video'
    setProgress('Creating data source…')
    const { data: upload } = await client.post<UploadResponse>(
      `/projects/${projectId}/data-sources`,
      { type },
    )
    setProgress('Registering existing video…')
    await client.post(`/data-sources/${upload.data_source.id}/confirm-upload`, {
      blob_hash: blobHash,
      workflow_id: wfValue || undefined,
    })
  }

  function finishUpload() {
    qc.invalidateQueries({ queryKey: ['data-sources', projectId] })
    setProgress(null)
    setUploading(false)
    setPct(null)
    if (fileRef.current) fileRef.current.value = ''
  }

  async function handleUpload(file: File) {
    setError(null)
    setUploading(true)
    setPct(null)
    try {
      // Hash first so a duplicate is caught before any bytes go over the wire.
      setProgress('Computing hash…')
      const blobHash = `sha256:${await sha256Hex(file)}`

      setProgress('Checking for duplicates…')
      const check = await checkDuplicate(projectId!, blobHash)
      if (check.exists) {
        // Pause the auto-flow and let the user decide (add / skip / close).
        setDupPrompt({
          file,
          blobHash,
          matches: check.matches,
          inCurrentProject: check.in_current_project,
        })
        return
      }

      await doFreshUpload(file, blobHash)
      finishUpload()
    } catch (err: unknown) {
      setError((err as Error).message ?? 'Upload failed')
      setUploading(false)
      setPct(null)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  async function handleAddExisting() {
    if (!dupPrompt) return
    const { file, blobHash } = dupPrompt
    setDupPrompt(null)
    try {
      await doRegisterExisting(file, blobHash)
      finishUpload()
    } catch (err: unknown) {
      setError((err as Error).message ?? 'Upload failed')
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  function dismissDupPrompt() {
    setDupPrompt(null)
    setUploading(false)
    setPct(null)
    setProgress(null)
    if (fileRef.current) fileRef.current.value = ''
  }

  const hasWorkflows = workflows && workflows.length > 0

  const dupProjectNames =
    dupPrompt &&
    [...new Set(dupPrompt.matches.map(m => m.project_name))].join(', ')

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {dupPrompt && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
          <div className="bg-surface-2 rounded-xl border border-border shadow-xl max-w-md w-full p-6 flex flex-col gap-4">
            <div>
              <h3 className="text-base font-semibold text-text-primary">
                {dupPrompt.inCurrentProject
                  ? 'Already in this project'
                  : 'Duplicate video found'}
              </h3>
              <p className="text-sm text-text-secondary mt-1">
                {dupPrompt.inCurrentProject ? (
                  <>This video is already a data source in this project.</>
                ) : (
                  <>
                    This exact video is already uploaded in{' '}
                    <span className="font-medium text-text-primary">{dupProjectNames}</span>.
                    Add it to this project without re-uploading?
                  </>
                )}
              </p>
            </div>

            <div className="flex justify-end gap-2">
              {dupPrompt.inCurrentProject ? (
                <>
                  <Link
                    to={`/projects/${dupPrompt.matches[0].project_id}/samples?source=${dupPrompt.matches[0].data_source_id}`}
                    className="text-sm font-medium text-iris-400 hover:text-iris-400 px-4 py-2"
                  >
                    View it →
                  </Link>
                  <button
                    onClick={dismissDupPrompt}
                    className="text-sm font-medium text-text-secondary hover:text-text-primary px-4 py-2 rounded-lg border border-border-strong"
                  >
                    Close
                  </button>
                </>
              ) : (
                <>
                  <button
                    onClick={dismissDupPrompt}
                    className="text-sm font-medium text-text-secondary hover:text-text-primary px-4 py-2 rounded-lg border border-border-strong"
                  >
                    Skip
                  </button>
                  <button
                    onClick={handleAddExisting}
                    className="text-sm font-medium text-white bg-iris hover:bg-iris-hover px-4 py-2 rounded-lg"
                  >
                    Add to this project
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="flex items-center gap-2 text-sm text-text-muted mb-6">
        <Link to={`/projects/${projectId}`} className="hover:text-iris-400">Project</Link>
        <span>/</span>
        <span className="text-text-primary font-medium">Data Sources</span>
      </div>

      <div className="flex items-start justify-between mb-4 gap-4">
        <h2 className="text-xl font-bold text-text-primary">Data Sources</h2>
        <div className="flex flex-col items-end gap-2">
          <div className="flex items-center gap-2">
            {hasWorkflows ? (
              <select
                value={wfValue}
                onChange={e => setSelectedWf(e.target.value)}
                disabled={uploading}
                title="Workflow to run automatically when the upload finishes"
                className="border border-border-strong bg-surface-2 rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-iris disabled:opacity-60"
              >
                <option value="">Just store (no processing)</option>
                {workflows.map(wf => (
                  <option key={wf.id} value={wf.id}>Run: {wf.name}</option>
                ))}
              </select>
            ) : (
              <button
                onClick={handleCreateIngestWorkflow}
                disabled={createWorkflow.isPending}
                title="Create a one-step workflow that extracts frames from uploads"
                className="border border-iris/40 text-iris-400 px-3 py-2 rounded-lg text-sm font-medium hover:bg-iris/10 disabled:opacity-60 transition-colors"
              >
                {createWorkflow.isPending ? 'Creating…' : '+ Add extract-frames workflow'}
              </button>
            )}
            <label className={`cursor-pointer bg-iris text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-iris-hover transition-colors whitespace-nowrap ${uploading ? 'opacity-60 cursor-not-allowed' : ''}`}>
              {uploading ? (progress ?? 'Uploading…') : '+ Upload video or image'}
              <input
                ref={fileRef}
                type="file"
                accept="video/*,image/*"
                className="hidden"
                disabled={uploading}
                onChange={e => {
                  const file = e.target.files?.[0]
                  if (file) handleUpload(file)
                }}
              />
            </label>
          </div>
          <p className="text-xs text-text-muted">
            {hasWorkflows
              ? wfValue
                ? 'The selected workflow runs automatically once the upload completes.'
                : 'Uploads are stored only — no frames extracted.'
              : 'No workflow yet — uploads are stored only until you add one.'}
          </p>
        </div>
      </div>

      {uploading && (
        <div className="mb-4">
          <div className="flex items-center justify-between text-xs text-text-secondary mb-1">
            <span>{progress ?? 'Uploading…'}</span>
            {pct !== null && <span>{Math.round(pct * 100)}%</span>}
          </div>
          <div className="h-2 w-full bg-surface-3 rounded-full overflow-hidden">
            <div
              className={`h-full bg-iris transition-all duration-150 ${pct === null ? 'animate-pulse w-full' : ''}`}
              style={pct === null ? undefined : { width: `${Math.round(pct * 100)}%` }}
            />
          </div>
        </div>
      )}

      {error && (
        <div className="bg-error/10 border border-error/30 text-error text-sm rounded-lg px-4 py-3 mb-4">
          {error}
        </div>
      )}

      {isLoading && <div className="text-center py-12 text-text-muted text-sm">Loading…</div>}

      {sources && sources.length === 0 && (
        <div className="bg-surface-2 rounded-xl border border-border shadow-sm p-10 text-center">
          <p className="text-sm font-medium text-text-primary">No data sources yet</p>
          <p className="text-xs text-text-muted mt-1">Upload a video or image to get started</p>
        </div>
      )}

      {sources && sources.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {sources.map(ds => (
            <SourceCard
              key={ds.id}
              ds={ds}
              projectId={projectId!}
              onDelete={id => deleteMutation.mutate(id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
