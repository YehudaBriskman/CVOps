import { useState, type FormEvent } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useProject, useUpdateProject, useDeleteProject } from '../api/projects'
import { useWorkflows, useCreateWorkflow } from '../api/workflows'
import {
  useOntologies,
  useCreateOntology,
  useLabelClasses,
  useCreateLabelClass,
  useDeleteLabelClass,
} from '../api/ontologies'
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

  if (isLoading) return <div className="p-6 text-sm text-text-muted">Loading…</div>

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <div className="flex items-center gap-2 text-sm text-text-muted mb-6">
        <Link to={`/projects/${id}`} className="hover:text-iris-400">Project</Link>
        <span>/</span>
        <span className="text-text-primary font-medium">Settings</span>
      </div>

      <h2 className="text-xl font-bold text-text-primary mb-6">Project Settings</h2>

      <form onSubmit={handleSave} className="bg-surface-2 rounded-xl border border-border shadow-sm p-6 mb-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-text-primary mb-1">Project name</label>
          <input
            type="text"
            required
            value={name}
            onChange={e => setName(e.target.value)}
            className="w-full border border-border-strong rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-focus"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-text-primary mb-1">Task type</label>
          <select
            value={taskType}
            onChange={e => setTaskType(e.target.value)}
            className="w-full border border-border-strong rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-focus"
          >
            <option value="detection">Detection</option>
            <option value="segmentation">Segmentation</option>
            <option value="classification">Classification</option>
          </select>
        </div>
        <button
          type="submit"
          disabled={updateProject.isPending}
          className="bg-iris text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-iris-hover disabled:opacity-60 transition-colors"
        >
          {saved ? '✓ Saved' : updateProject.isPending ? 'Saving…' : 'Save changes'}
        </button>
      </form>

      <div className="bg-surface-2 rounded-xl border border-border shadow-sm p-6 mb-6 space-y-4">
        <div>
          <h3 className="text-sm font-bold text-text-primary">Ingest workflow</h3>
          <p className="text-xs text-text-secondary mt-1">
            Runs automatically on every uploaded data source to extract frames into samples.
          </p>
        </div>

        {workflows && workflows.length > 0 ? (
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1">Default ingest workflow</label>
            <select
              value={project?.default_ingest_workflow_id ?? ''}
              onChange={e => handleSelectIngest(e.target.value)}
              disabled={updateProject.isPending}
              className="w-full border border-border-strong rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-focus"
            >
              <option value="">None</option>
              {workflows.map(wf => (
                <option key={wf.id} value={wf.id}>{wf.name}</option>
              ))}
            </select>
            {ingestSaved && <p className="text-xs text-success mt-1">✓ Saved</p>}
          </div>
        ) : (
          <p className="text-sm text-text-secondary">
            No workflows yet. Create the default extract-frames workflow to enable ingest.
          </p>
        )}

        <button
          onClick={handleCreateIngestWorkflow}
          disabled={createWorkflow.isPending || updateProject.isPending}
          className="border border-iris/30 text-iris-400 px-4 py-2 rounded-lg text-sm font-medium hover:bg-iris/10 disabled:opacity-60 transition-colors"
        >
          {createWorkflow.isPending ? 'Creating…' : 'Create extract-frames workflow'}
        </button>
      </div>

      {id && <LabelClassesCard projectId={id} />}

      <div className="bg-surface-2 rounded-xl border border-error/30 shadow-sm p-6">
        <h3 className="text-sm font-bold text-error mb-2">Danger zone</h3>
        <p className="text-xs text-text-secondary mb-4">Deleting a project is permanent and cannot be undone.</p>
        {!confirmDelete ? (
          <button
            onClick={() => setConfirmDelete(true)}
            className="border border-error/30 text-error px-4 py-2 rounded-lg text-sm hover:bg-error/10 transition-colors"
          >
            Delete project
          </button>
        ) : (
          <div className="flex items-center gap-3">
            <p className="text-sm text-text-primary">Are you sure?</p>
            <button
              onClick={handleDelete}
              disabled={deleteProject.isPending}
              className="bg-error text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-error disabled:opacity-60"
            >
              Yes, delete
            </button>
            <button
              onClick={() => setConfirmDelete(false)}
              className="border border-border-strong text-text-secondary px-4 py-2 rounded-lg text-sm hover:bg-surface-3"
            >
              Cancel
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function LabelClassesCard({ projectId }: { projectId: string }) {
  const { data: ontologies } = useOntologies(projectId)
  const createOntology = useCreateOntology(projectId)
  // One label set per project for now; human_review resolves it as the
  // project's ontology and seeds each CVAT task's classes from it.
  const ontology = ontologies?.[0]
  const { data: classes } = useLabelClasses(ontology?.id)
  const createClass = useCreateLabelClass(ontology?.id)
  const deleteClass = useDeleteLabelClass(ontology?.id)

  const [key, setKey] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [color, setColor] = useState('#7B6CF6')

  async function handleAdd(e: FormEvent) {
    e.preventDefault()
    if (!ontology?.id || !key.trim()) return
    const sortOrder = classes && classes.length ? Math.max(...classes.map(c => c.sort_order)) + 1 : 0
    await createClass.mutateAsync({
      class_key: key.trim(),
      display_name: displayName.trim() || key.trim(),
      color,
      sort_order: sortOrder,
    })
    setKey('')
    setDisplayName('')
    setColor('#7B6CF6')
  }

  return (
    <div className="bg-surface-2 rounded-xl border border-border shadow-sm p-6 mb-6 space-y-4">
      <div>
        <h3 className="text-sm font-bold text-text-primary">Label classes</h3>
        <p className="text-xs text-text-secondary mt-1">
          The classes reviewers annotate with in CVAT — defined on the project ontology and
          pushed into every human-review task.
        </p>
      </div>

      {!ontology ? (
        <button
          onClick={() => createOntology.mutate({ name: 'default' })}
          disabled={createOntology.isPending}
          className="border border-iris/30 text-iris-400 px-4 py-2 rounded-lg text-sm font-medium hover:bg-iris/10 disabled:opacity-60 transition-colors"
        >
          {createOntology.isPending ? 'Creating…' : 'Create label set'}
        </button>
      ) : (
        <>
          {classes && classes.length > 0 ? (
            <ul className="space-y-2">
              {classes.map(c => (
                <li
                  key={c.id}
                  className="flex items-center gap-3 rounded-lg border border-border px-3 py-2"
                >
                  <span
                    className="h-4 w-4 rounded-full border border-border-strong"
                    style={{ backgroundColor: c.color }}
                    aria-hidden
                  />
                  <span className="text-sm text-text-primary">{c.display_name}</span>
                  <span className="text-xs text-text-muted font-mono">{c.class_key}</span>
                  <button
                    onClick={() => deleteClass.mutate(c.id)}
                    disabled={deleteClass.isPending}
                    className="ml-auto text-text-muted hover:text-error disabled:opacity-60"
                    aria-label={`Delete ${c.display_name}`}
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-text-secondary">No classes yet. Add the first one below.</p>
          )}

          <form onSubmit={handleAdd} className="flex items-end gap-2">
            <div className="flex-1">
              <label className="block text-sm font-medium text-text-primary mb-1">Class key</label>
              <input
                type="text"
                required
                value={key}
                onChange={e => setKey(e.target.value)}
                placeholder="plane"
                className="w-full border border-border-strong rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-focus"
              />
            </div>
            <div className="flex-1">
              <label className="block text-sm font-medium text-text-primary mb-1">Display name</label>
              <input
                type="text"
                value={displayName}
                onChange={e => setDisplayName(e.target.value)}
                placeholder="Plane"
                className="w-full border border-border-strong rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-focus"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1">Color</label>
              <input
                type="color"
                value={color}
                onChange={e => setColor(e.target.value)}
                className="h-10 w-12 cursor-pointer rounded-lg border border-border-strong"
              />
            </div>
            <button
              type="submit"
              disabled={createClass.isPending || !key.trim()}
              className="bg-iris text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-iris-hover disabled:opacity-60 transition-colors"
            >
              {createClass.isPending ? 'Adding…' : 'Add'}
            </button>
          </form>
          {createClass.isError && (
            <p className="text-xs text-error">Couldn’t add class — the key may already exist.</p>
          )}
        </>
      )}
    </div>
  )
}
