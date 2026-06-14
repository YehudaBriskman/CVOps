import { useState, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { client } from '../lib/client'

interface DataSource {
  id: string
  type: string
  status: string
  blob_hash: string | null
  external_uri: string | null
  created_at: string
}

function useDataSources(projectId: string | undefined) {
  return useQuery<DataSource[]>({
    queryKey: ['data-sources', projectId],
    queryFn: async () => {
      const { data } = await client.get<DataSource[]>(`/projects/${projectId}/data-sources`)
      return data
    },
    enabled: !!projectId,
  })
}

const STATUS_BADGE: Record<string, string> = {
  pending:   'bg-amber-100 text-amber-700',
  confirmed: 'bg-green-100 text-green-700',
  failed:    'bg-red-100 text-red-700',
}

export default function DataSources() {
  const { id: projectId } = useParams<{ id: string }>()
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const { data: sources, isLoading } = useDataSources(projectId)

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => { await client.delete(`/data-sources/${id}`) },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['data-sources', projectId] }),
  })

  async function handleUpload(file: File) {
    setError(null)
    setUploading(true)
    try {
      setProgress('Creating data source…')
      const { data: upload } = await client.post<{
        data_source: DataSource
        presigned_put_url: string | null
      }>(`/projects/${projectId}/data-sources`, { type: 'video' })

      if (upload.presigned_put_url) {
        setProgress('Uploading to storage…')
        const put = await fetch(upload.presigned_put_url, { method: 'PUT', body: file })
        if (!put.ok) throw new Error(`Upload failed: ${put.status}`)
      }

      setProgress('Computing hash…')
      const buf = await file.arrayBuffer()
      const digest = await crypto.subtle.digest('SHA-256', buf)
      const hex = [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, '0')).join('')
      const blobHash = `sha256:${hex}`

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
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center gap-2 text-sm text-slate-400 mb-6">
        <Link to={`/projects/${projectId}`} className="hover:text-indigo-600">Project</Link>
        <span>/</span>
        <span className="text-slate-700 font-medium">Data Sources</span>
      </div>

      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold text-slate-800">Data Sources</h2>
        <label className={`cursor-pointer bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors ${uploading ? 'opacity-60 cursor-not-allowed' : ''}`}>
          {uploading ? (progress ?? 'Uploading…') : '+ Upload video'}
          <input
            ref={fileRef}
            type="file"
            accept="video/*"
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
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 mb-4">
          {error}
        </div>
      )}

      {isLoading && <div className="text-center py-12 text-slate-400 text-sm">Loading…</div>}

      {sources && sources.length === 0 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-10 text-center">
          <p className="text-sm font-medium text-slate-700">No data sources yet</p>
          <p className="text-xs text-slate-400 mt-1">Upload a video to get started</p>
        </div>
      )}

      {sources && sources.length > 0 && (
        <div className="space-y-2">
          {sources.map(ds => (
            <div key={ds.id} className="flex items-center justify-between bg-white rounded-xl border border-slate-200 shadow-sm px-5 py-3">
              <div>
                <p className="text-sm font-medium text-slate-800 capitalize">{ds.type}</p>
                <p className="text-xs text-slate-400 mt-0.5 font-mono">{ds.id.slice(0, 8)}…</p>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_BADGE[ds.status] ?? 'bg-slate-100 text-slate-500'}`}>
                  {ds.status}
                </span>
                <button
                  onClick={() => deleteMutation.mutate(ds.id)}
                  className="text-xs text-red-400 hover:text-red-600 transition-colors"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
