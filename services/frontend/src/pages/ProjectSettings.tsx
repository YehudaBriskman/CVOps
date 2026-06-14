import { useState, type FormEvent } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useProject, useUpdateProject, useDeleteProject } from '../api/projects'

export default function ProjectSettings() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: project, isLoading } = useProject(id)
  const updateProject = useUpdateProject(id)
  const deleteProject = useDeleteProject()

  const [name, setName] = useState('')
  const [taskType, setTaskType] = useState('')
  const [saved, setSaved] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  // Sync form once project loads
  if (project && name === '' && taskType === '') {
    setName(project.name)
    setTaskType(project.task_type)
  }

  async function handleSave(e: FormEvent) {
    e.preventDefault()
    await updateProject.mutateAsync({ name, task_type: taskType })
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  async function handleDelete() {
    if (!id) return
    await deleteProject.mutateAsync(id)
    navigate('/projects', { replace: true })
  }

  if (isLoading) return <div className="p-6 text-sm text-slate-400">Loading…</div>

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <div className="flex items-center gap-2 text-sm text-slate-400 mb-6">
        <Link to={`/projects/${id}`} className="hover:text-indigo-600">Project</Link>
        <span>/</span>
        <span className="text-slate-700 font-medium">Settings</span>
      </div>

      <h2 className="text-xl font-bold text-slate-800 mb-6">Project Settings</h2>

      <form onSubmit={handleSave} className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Project name</label>
          <input
            type="text"
            required
            value={name}
            onChange={e => setName(e.target.value)}
            className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Task type</label>
          <select
            value={taskType}
            onChange={e => setTaskType(e.target.value)}
            className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="detection">Detection</option>
            <option value="segmentation">Segmentation</option>
            <option value="classification">Classification</option>
          </select>
        </div>
        <button
          type="submit"
          disabled={updateProject.isPending}
          className="bg-indigo-600 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-60 transition-colors"
        >
          {saved ? '✓ Saved' : updateProject.isPending ? 'Saving…' : 'Save changes'}
        </button>
      </form>

      <div className="bg-white rounded-xl border border-red-200 shadow-sm p-6">
        <h3 className="text-sm font-bold text-red-700 mb-2">Danger zone</h3>
        <p className="text-xs text-slate-500 mb-4">Deleting a project is permanent and cannot be undone.</p>
        {!confirmDelete ? (
          <button
            onClick={() => setConfirmDelete(true)}
            className="border border-red-300 text-red-600 px-4 py-2 rounded-lg text-sm hover:bg-red-50 transition-colors"
          >
            Delete project
          </button>
        ) : (
          <div className="flex items-center gap-3">
            <p className="text-sm text-slate-700">Are you sure?</p>
            <button
              onClick={handleDelete}
              disabled={deleteProject.isPending}
              className="bg-red-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-red-700 disabled:opacity-60"
            >
              Yes, delete
            </button>
            <button
              onClick={() => setConfirmDelete(false)}
              className="border border-slate-300 text-slate-600 px-4 py-2 rounded-lg text-sm hover:bg-slate-50"
            >
              Cancel
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
