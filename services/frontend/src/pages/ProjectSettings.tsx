import { useState, type FormEvent } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useProject, useUpdateProject, useDeleteProject } from '../api/projects'
import { useWorkflows, useCreateWorkflow } from '../api/workflows'
import { INGEST_WORKFLOW_DEFINITION, INGEST_WORKFLOW_NAME } from '../lib/ingest'

export default function ProjectSettings() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: project, isLoading } = useProject(id)
  const { data: workflows } = useWorkflows(id)
  const updateProject = useUpdateProject(id)
  const createWorkflow = useCreateWorkflow()
  const deleteProject = useDeleteProject()

  const [name, setName] = useState('')
  const [taskType, setTaskType] = useState('')
  const [saved, setSaved] = useState(false)
  const [ingestSaved, setIngestSaved] = useState(false)
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

  async function handleSelectIngest(workflowId: string) {
    await updateProject.mutateAsync({ default_ingest_workflow_id: workflowId || null })
    setIngestSaved(true)
    setTimeout(() => setIngestSaved(false), 2000)
  }

  async function handleCreateIngestWorkflow() {
    if (!id) return
    const wf = await createWorkflow.mutateAsync({
      projectId: id,
      name: INGEST_WORKFLOW_NAME,
      definition: INGEST_WORKFLOW_DEFINITION,
    })
    await handleSelectIngest(wf.id)
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

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-6 space-y-4">
        <div>
          <h3 className="text-sm font-bold text-slate-800">Ingest workflow</h3>
          <p className="text-xs text-slate-500 mt-1">
            Runs automatically on every uploaded data source to extract frames into samples.
          </p>
        </div>

        {workflows && workflows.length > 0 ? (
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Default ingest workflow</label>
            <select
              value={project?.default_ingest_workflow_id ?? ''}
              onChange={e => handleSelectIngest(e.target.value)}
              disabled={updateProject.isPending}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="">None</option>
              {workflows.map(wf => (
                <option key={wf.id} value={wf.id}>{wf.name}</option>
              ))}
            </select>
            {ingestSaved && <p className="text-xs text-green-600 mt-1">✓ Saved</p>}
          </div>
        ) : (
          <p className="text-sm text-slate-500">
            No workflows yet. Create the default extract-frames workflow to enable ingest.
          </p>
        )}

        <button
          onClick={handleCreateIngestWorkflow}
          disabled={createWorkflow.isPending || updateProject.isPending}
          className="border border-indigo-300 text-indigo-600 px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-50 disabled:opacity-60 transition-colors"
        >
          {createWorkflow.isPending ? 'Creating…' : 'Create extract-frames workflow'}
        </button>
      </div>

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
