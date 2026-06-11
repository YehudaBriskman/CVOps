import { useState } from 'react'
import { Link } from 'react-router-dom'
import { MOCK_PROJECTS } from '../mock/data'

const STATUS_BADGE: Record<string, string> = {
  running:   'bg-amber-100 text-amber-700',
  completed: 'bg-green-100 text-green-700',
  failed:    'bg-red-100   text-red-700',
}

export default function Projects() {
  const [showForm, setShowForm] = useState(false)
  const [newName,  setNewName]  = useState('')
  const [taskType, setTaskType] = useState('detection')

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Title row */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Projects</h2>
          <p className="text-sm text-slate-400 mt-0.5">Each project is one ML problem domain</p>
        </div>
        <button
          onClick={() => setShowForm(s => !s)}
          className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors"
        >
          + New Project
        </button>
      </div>

      {/* Inline create form */}
      {showForm && (
        <div className="mb-6 p-4 bg-white rounded-xl border border-indigo-200 shadow-sm">
          <p className="text-sm font-semibold text-slate-800 mb-3">New Project</p>
          <div className="flex flex-wrap gap-3 items-end">
            <div className="flex-1 min-w-48">
              <label className="text-xs text-slate-500 mb-1 block">Project name</label>
              <input
                type="text"
                value={newName}
                onChange={e => setNewName(e.target.value)}
                placeholder="e.g. Road Traffic Detection"
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
              />
            </div>
            <div className="w-44">
              <label className="text-xs text-slate-500 mb-1 block">Task type</label>
              <select
                value={taskType}
                onChange={e => setTaskType(e.target.value)}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
              >
                <option value="detection">Detection</option>
                <option value="segmentation">Segmentation</option>
                <option value="classification">Classification</option>
              </select>
            </div>
            <button
              onClick={() => { setShowForm(false); setNewName('') }}
              className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors"
            >
              Create
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="text-slate-500 px-3 py-2 rounded-lg text-sm hover:bg-slate-100 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Project grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {MOCK_PROJECTS.map(project => (
          <Link
            key={project.id}
            to={`/projects/${project.id}`}
            className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 hover:border-indigo-300 hover:shadow-md transition-all group"
          >
            <div className="flex items-start justify-between gap-2 mb-4">
              <h3 className="text-base font-bold text-slate-900 group-hover:text-indigo-700 transition-colors leading-tight">
                {project.name}
              </h3>
              <span className="text-xs bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full font-medium capitalize flex-shrink-0">
                {project.task_type}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-x-4 gap-y-2 mb-4">
              {[
                { label: 'Samples',  value: project.sample_count.toLocaleString() },
                { label: 'Runs',     value: project.run_count },
                { label: 'Datasets', value: project.dataset_count },
                { label: 'Models',   value: project.model_count },
              ].map(({ label, value }) => (
                <div key={label}>
                  <p className="text-xs text-slate-400">{label}</p>
                  <p className="text-sm font-semibold text-slate-800">{value}</p>
                </div>
              ))}
            </div>

            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400">Last run</span>
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${STATUS_BADGE[project.last_run_status] ?? 'bg-slate-100 text-slate-500'}`}>
                {project.last_run_status}
              </span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
