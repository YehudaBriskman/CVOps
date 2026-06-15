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
  type UploadResponse,
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
      cls = 'bg-red-100 text-red-700'
      break
    case 'pending':
      label = 'Uploading'
      cls = 'bg-amber-100 text-amber-700'
      break
    case 'uploaded':
      if (ds.type === 'image') {
        label = 'Ready'
        cls = 'bg-green-100 text-green-700'
      } else {
        label = 'Queued'
        cls = 'bg-slate-100 text-slate-500'
        spinner = true
      }
      break
    case 'ingesting':
      label = 'Extracting frames'
      cls = 'bg-indigo-100 text-indigo-700'
      spinner = true
      break
    case 'ingested':
      label = 'Ready'
      cls = 'bg-green-100 text-green-700'
      break
    default:
      label = ds.status
      cls = 'bg-slate-100 text-slate-500'
  }

  return (
    <span className={`inline-flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full font-medium ${cls}`}>
      {spinner && <span className="w-3 h-3 border-2 border-indigo-300 border-t-indigo-600 rounded-full animate-spin" />}
      {label}
    </span>
  )
}

function SourcePreview({ ds }: { ds: DataSource }) {
  const { data, isLoading, isError } = useDataSourceUrl(ds.id, ds.blob_hash != null)

  if (ds.external_uri && !ds.blob_hash) {
    return (
      <div className="aspect-video bg-slate-50 flex items-center justify-center px-4">
        <a href={ds.external_uri} target="_blank" rel="noreferrer" className="text-xs text-indigo-600 hover:underline break-all text-center">
          {ds.external_uri}
        </a>
      </div>
    )
  }

  if (ds.blob_hash == null) {
    return <div className="aspect-video bg-slate-100" />
  }

  if (isLoading) {
    return (
      <div className="aspect-video bg-slate-100 flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-slate-300 border-t-slate-500 rounded-full animate-spin" />
      </div>
    )
  }

  if (isError || !data?.url) {
    return (
      <div className="aspect-video bg-slate-50 flex items-center justify-center text-xs text-slate-400">
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
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
      <SourcePreview ds={ds} />
      <div className="p-4 flex flex-col gap-3 flex-1">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-sm font-medium text-slate-800 capitalize">{ds.type.replace('_', ' ')}</p>
            <p className="text-xs text-slate-400 mt-0.5 font-mono">{ds.id.slice(0, 8)}…</p>
          </div>
          <StatusBadge ds={ds} />
        </div>

        <div className="flex items-center justify-between mt-auto">
          {frames > 0 ? (
            <Link
              to={`/projects/${projectId}/samples?source=${ds.id}`}
              className="text-xs font-medium text-indigo-600 hover:text-indigo-700"
            >
              View {frames} frame{frames === 1 ? '' : 's'} →
            </Link>
          ) : (
            <span className="text-xs text-slate-400">No frames yet</span>
          )}
          <div className="flex items-center gap-3">
            {ds.latest_run_id && (
              <Link
                to={`/runs/${ds.latest_run_id}`}
                className="text-xs font-medium text-indigo-600 hover:text-indigo-700"
              >
                View run →
              </Link>
            )}
            <button
              onClick={() => onDelete(ds.id)}
              className="text-xs text-red-400 hover:text-red-600 transition-colors"
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

  async function handleUpload(file: File) {
    setError(null)
    setUploading(true)
    setPct(null)
    try {
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
      setProgress('Computing hash…')
      const blobHash = `sha256:${await sha256Hex(file)}`

      setProgress('Confirming upload…')
      await client.post(`/data-sources/${upload.data_source.id}/confirm-upload`, {
        blob_hash: blobHash,
        // Empty string → omit, so the backend treats it as "no workflow".
        workflow_id: wfValue || undefined,
      })

      qc.invalidateQueries({ queryKey: ['data-sources', projectId] })
      setProgress(null)
    } catch (err: unknown) {
      setError((err as Error).message ?? 'Upload failed')
    } finally {
      setUploading(false)
      setPct(null)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const hasWorkflows = workflows && workflows.length > 0

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center gap-2 text-sm text-slate-400 mb-6">
        <Link to={`/projects/${projectId}`} className="hover:text-indigo-600">Project</Link>
        <span>/</span>
        <span className="text-slate-700 font-medium">Data Sources</span>
      </div>

      <div className="flex items-start justify-between mb-4 gap-4">
        <h2 className="text-xl font-bold text-slate-800">Data Sources</h2>
        <div className="flex flex-col items-end gap-2">
          <div className="flex items-center gap-2">
            {hasWorkflows ? (
              <select
                value={wfValue}
                onChange={e => setSelectedWf(e.target.value)}
                disabled={uploading}
                title="Workflow to run automatically when the upload finishes"
                className="border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-60"
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
                className="border border-indigo-300 text-indigo-600 px-3 py-2 rounded-lg text-sm font-medium hover:bg-indigo-50 disabled:opacity-60 transition-colors"
              >
                {createWorkflow.isPending ? 'Creating…' : '+ Add extract-frames workflow'}
              </button>
            )}
            <label className={`cursor-pointer bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors whitespace-nowrap ${uploading ? 'opacity-60 cursor-not-allowed' : ''}`}>
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
          <p className="text-xs text-slate-400">
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
          <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
            <span>{progress ?? 'Uploading…'}</span>
            {pct !== null && <span>{Math.round(pct * 100)}%</span>}
          </div>
          <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
            <div
              className={`h-full bg-indigo-600 transition-all duration-150 ${pct === null ? 'animate-pulse w-full' : ''}`}
              style={pct === null ? undefined : { width: `${Math.round(pct * 100)}%` }}
            />
          </div>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 mb-4">
          {error}
        </div>
      )}

      {isLoading && <div className="text-center py-12 text-slate-400 text-sm">Loading…</div>}

      {sources && sources.length === 0 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-10 text-center">
          <p className="text-sm font-medium text-slate-700">No data sources yet</p>
          <p className="text-xs text-slate-400 mt-1">Upload a video or image to get started</p>
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
