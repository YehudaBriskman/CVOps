import { useRef, useState } from 'react'
import { toast } from '../store/toast'
import { useCvatModels, useDeployCvatModel, useDeleteCvatModel } from '../api/cvat'

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
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-slate-800">Deployed Models</h2>
          <p className="text-sm text-slate-500 mt-0.5">Models currently deployed in CVAT via Nuclio</p>
        </div>
        <button
          onClick={() => setShowForm(v => !v)}
          className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors"
        >
          + Deploy Model
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={handleDeploy}
          className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-6 flex flex-col gap-3"
        >
          <div className="flex gap-3 items-end">
            <div className="flex-1">
              <label className="block text-xs font-medium text-slate-600 mb-1">Model name</label>
              <input
                required
                autoFocus
                value={modelName}
                onChange={e => setModelName(e.target.value)}
                placeholder="e.g. yolov8n"
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div className="flex-1">
              <label className="block text-xs font-medium text-slate-600 mb-1">Weights file (.pt)</label>
              <input
                required
                ref={fileRef}
                type="file"
                accept=".pt"
                onChange={e => setFile(e.target.files?.[0] ?? null)}
                className="w-full text-sm text-slate-600 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
              />
            </div>
          </div>

          <div className="flex gap-2 items-center">
            <button
              type="submit"
              disabled={deploy.isPending || !file}
              className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-60 flex items-center gap-2"
            >
              {deploy.isPending && (
                <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                </svg>
              )}
              {deploy.isPending ? 'Deploying…' : 'Deploy'}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              disabled={deploy.isPending}
              className="border border-slate-300 text-slate-600 px-4 py-2 rounded-lg text-sm hover:bg-slate-50 disabled:opacity-60"
            >
              Cancel
            </button>
            {deploy.isPending && (
              <span className="text-xs text-slate-400">Building Docker image, may take a few minutes…</span>
            )}
          </div>
        </form>
      )}

      {isLoading && (
        <div className="flex items-center justify-center py-16 gap-3 text-slate-400 text-sm">
          <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
          </svg>
          Loading models…
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
          Failed to load models
        </div>
      )}

      {models && models.length === 0 && (
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm p-10 text-center">
          <p className="text-sm font-medium text-slate-700">No models deployed</p>
          <p className="text-xs text-slate-400 mt-1">Click "Deploy Model" to upload a .pt file</p>
        </div>
      )}

      {models && models.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {models.map(m => (
            <div
              key={m.id}
              className="bg-white rounded-xl border border-slate-200 shadow-sm px-5 py-4"
            >
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-semibold text-slate-800">{m.name}</p>
                  <p className="text-xs text-slate-400 mt-1 font-mono">{m.id}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs bg-indigo-50 text-indigo-600 font-medium px-2 py-0.5 rounded-full capitalize">
                    {m.kind || 'detector'}
                  </span>
                  <button
                    onClick={() => handleDelete(m.id, m.name)}
                    disabled={deleteModel.isPending}
                    className="text-slate-400 hover:text-red-500 transition-colors disabled:opacity-40"
                    title="Delete model"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
                    </svg>
                  </button>
                </div>
              </div>
              {m.description && (
                <p className="text-xs text-slate-500 mt-2">{m.description}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
