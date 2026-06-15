import { useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { client } from '../lib/client'
import { sha256Hex } from '../lib/hash'
import { toast } from '../store/toast'
import {
  type DataSource,
  type UploadResponse,
  useDataSourceUrl,
  useDataSources,
  useDeleteDataSource,
} from '../api/data-sources'

function errMessage(err: unknown): string {
  if (err instanceof Error) return err.message
  if (typeof err === 'string') return err
  return 'Upload failed'
}

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
  const videoRef = useRef<HTMLInputElement>(null)
  const imageRef = useRef<HTMLInputElement>(null)
  const folderRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const { data: sources, isLoading } = useDataSources(projectId)
  const deleteMutation = useDeleteDataSource(projectId)

  // One file → one data source: register → presigned PUT → confirm-upload.
  // `type` is the backend DataSource.type ('video' | 'image'); the value drives
  // whether the project's default ingest workflow frame-extracts (video) or
  // leaves the source as a ready image.
  async function uploadOne(file: File, type: 'video' | 'image') {
    const { data: upload } = await client.post<UploadResponse>(
      `/projects/${projectId}/data-sources`,
      { type },
    )

    if (upload.presigned_put_url) {
      const put = await fetch(upload.presigned_put_url, { method: 'PUT', body: file })
      if (!put.ok) throw new Error(`Upload failed: ${put.status}`)
    }

    const blobHash = `sha256:${await sha256Hex(file)}`
    await client.post(`/data-sources/${upload.data_source.id}/confirm-upload`, { blob_hash: blobHash })
  }

  // Drives one or more files through `uploadOne` sequentially, reporting
  // aggregate progress. A folder or multi-select lands here as several files,
  // each registered as its own image data source (the backend has no
  // folder-aware ingest, so N images is the faithful representation).
  async function handleUpload(files: File[]) {
    if (files.length === 0) return
    setError(null)
    setUploading(true)
    let failed = 0
    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i]
        const type: 'video' | 'image' = file.type.startsWith('image/') ? 'image' : 'video'
        const label = files.length > 1 ? `Uploading ${i + 1} of ${files.length}…` : 'Uploading…'
        setProgress(label)
        try {
          await uploadOne(file, type)
        } catch (err: unknown) {
          failed += 1
          toast.error(`Failed to upload ${file.name}`, errMessage(err))
        }
        // Surface each finished source as soon as it lands.
        qc.invalidateQueries({ queryKey: ['data-sources', projectId] })
      }

      const ok = files.length - failed
      if (failed > 0 && ok === 0) {
        setError(`All ${failed} upload${failed === 1 ? '' : 's'} failed`)
      } else if (failed > 0) {
        toast.warning(`${ok} uploaded, ${failed} failed`)
      } else if (files.length > 1) {
        toast.success(`Uploaded ${files.length} files`)
      }
    } finally {
      setUploading(false)
      setProgress(null)
      if (videoRef.current) videoRef.current.value = ''
      if (imageRef.current) imageRef.current.value = ''
      if (folderRef.current) folderRef.current.value = ''
    }
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center gap-2 text-sm text-text-muted mb-6">
        <Link to={`/projects/${projectId}`} className="hover:text-iris-400">Project</Link>
        <span>/</span>
        <span className="text-text-primary font-medium">Data Sources</span>
      </div>

      <div className="flex items-center justify-between gap-3 mb-4">
        <h2 className="text-xl font-bold text-text-primary">Data Sources</h2>
        <div className="flex items-center gap-2">
          {uploading ? (
            <span className="inline-flex items-center gap-2 bg-iris/10 text-iris-400 px-4 py-2 rounded-lg text-sm font-medium">
              <span className="w-3.5 h-3.5 border-2 border-iris-400 border-t-transparent rounded-full animate-spin" />
              {progress ?? 'Uploading…'}
            </span>
          ) : (
            <>
              <label className="cursor-pointer bg-iris text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-iris-hover transition-colors">
                + Video
                <input
                  ref={videoRef}
                  type="file"
                  accept="video/*"
                  className="hidden"
                  onChange={e => {
                    const file = e.target.files?.[0]
                    if (file) handleUpload([file])
                  }}
                />
              </label>
              <label className="cursor-pointer bg-surface-3 text-text-primary border border-border px-4 py-2 rounded-lg text-sm font-medium hover:bg-surface-1 transition-colors">
                + Images
                <input
                  ref={imageRef}
                  type="file"
                  accept="image/*"
                  multiple
                  className="hidden"
                  onChange={e => handleUpload(Array.from(e.target.files ?? []))}
                />
              </label>
              <label className="cursor-pointer bg-surface-3 text-text-primary border border-border px-4 py-2 rounded-lg text-sm font-medium hover:bg-surface-1 transition-colors">
                + Folder
                <input
                  ref={folderRef}
                  type="file"
                  accept="image/*"
                  multiple
                  // @ts-expect-error — non-standard but widely supported directory picker
                  webkitdirectory=""
                  className="hidden"
                  onChange={e => {
                    // A directory picker yields every file in the tree; keep only images.
                    const imgs = Array.from(e.target.files ?? []).filter(f => f.type.startsWith('image/'))
                    handleUpload(imgs)
                  }}
                />
              </label>
            </>
          )}
        </div>
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
