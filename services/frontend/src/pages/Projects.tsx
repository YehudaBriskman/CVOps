import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useProjects, useCreateProject } from '../api/projects'

export default function Projects() {
  const { data: projects, isLoading, error } = useProjects()
  const createProject = useCreateProject()
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [taskType, setTaskType] = useState('detection')

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    await createProject.mutateAsync({ name, task_type: taskType })
    setName('')
    setShowForm(false)
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-slate-800">Projects</h2>
          <p className="text-sm text-slate-500 mt-0.5">Each project is one ML problem domain</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors"
        >
          + New Project
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4 flex gap-3 items-end">
          <div className="flex-1">
            <label className="block text-xs font-medium text-slate-600 mb-1">Name</label>
            <input
              required
              autoFocus
              value={name}
              onChange={e => setName(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="My project"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Task type</label>
            <select
              value={taskType}
              onChange={e => setTaskType(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="detection">Detection</option>
              <option value="segmentation">Segmentation</option>
              <option value="classification">Classification</option>
            </select>
          </div>
          <button
            type="submit"
            disabled={createProject.isPending}
            className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-60"
          >
            Create
          </button>
          <button
            type="button"
            onClick={() => setShowForm(false)}
            className="border border-slate-300 text-slate-600 px-4 py-2 rounded-lg text-sm hover:bg-slate-50"
          >
            Cancel
          </button>
        </form>
      )}

      {isLoading && (
        <div className="text-center py-12 text-slate-400 text-sm">Loading…</div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
          Failed to load projects
        </div>
      )}

      {projects && projects.length === 0 && (
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm p-10 text-center">
          <p className="text-sm font-medium text-slate-700">No projects yet</p>
          <p className="text-xs text-slate-400 mt-1">Create your first project to get started</p>
        </div>
      )}

      {projects && projects.length > 0 && (
        <div className="grid gap-3">
          {projects.map(p => (
            <Link
              key={p.id}
              to={`/projects/${p.id}`}
              className="flex items-center justify-between bg-white rounded-xl border border-slate-200 shadow-sm px-5 py-4 hover:border-indigo-300 hover:shadow-md transition-all"
            >
              <div>
                <p className="font-semibold text-slate-800">{p.name}</p>
                <p className="text-xs text-slate-400 mt-0.5 capitalize">{p.task_type}</p>
              </div>
              <span className="text-slate-300 text-lg">›</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
