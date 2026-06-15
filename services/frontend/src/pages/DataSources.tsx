import { useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { client } from '../lib/client'
import { sha256Hex } from '../lib/hash'
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
          <button
            onClick={() => onDelete(ds.id)}
            className="text-xs text-error hover:text-error transition-colors"
          >
            Delete
          </button>
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
  const [error, setError] = useState<string | null>(null)

  const { data: sources, isLoading } = useDataSources(projectId)
  const deleteMutation = useDeleteDataSource(projectId)

  async function handleUpload(file: File) {
    setError(null)
    setUploading(true)
    try {
      const type = file.type.startsWith('image/') ? 'image' : 'video'
      setProgress('Creating data source…')
      const { data: upload } = await client.post<UploadResponse>(
        `/projects/${projectId}/data-sources`,
        { type },
      )

      if (upload.presigned_put_url) {
        setProgress('Uploading to storage…')
        const put = await fetch(upload.presigned_put_url, { method: 'PUT', body: file })
        if (!put.ok) throw new Error(`Upload failed: ${put.status}`)
      }

      setProgress('Computing hash…')
      const blobHash = `sha256:${await sha256Hex(file)}`

      setProgress('Confirming upload…')
      await client.post(`/data-sources/${upload.data_source.id}/confirm-upload`, { blob_hash: blobHash })

      qc.invalidateQueries({ queryKey: ['data-sources', projectId] })
      setProgress(null)
    } catch (err: unknown) {
      setError((err as Error).message ?? 'Upload failed')
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center gap-2 text-sm text-text-muted mb-6">
        <Link to={`/projects/${projectId}`} className="hover:text-iris-400">Project</Link>
        <span>/</span>
        <span className="text-text-primary font-medium">Data Sources</span>
      </div>

      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold text-text-primary">Data Sources</h2>
        <label className={`cursor-pointer bg-iris text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-iris-hover transition-colors ${uploading ? 'opacity-60 cursor-not-allowed' : ''}`}>
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
