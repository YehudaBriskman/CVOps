import { useParams, Link, useNavigate } from 'react-router-dom'
import { useWorkflows, useCreateWorkflow, useDeleteWorkflow } from '../api/workflows'

export default function Workflows() {
  const { id: projectId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: workflows, isLoading } = useWorkflows(projectId)
  const createWorkflow = useCreateWorkflow()
  const deleteWorkflow = useDeleteWorkflow()

  async function handleNew() {
    if (!projectId) return
    const wf = await createWorkflow.mutateAsync({
      projectId,
      name: 'New workflow',
      definition: { steps: [], edges: [] },
    })
    navigate(`/workflows/${wf.id}`)
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center gap-2 text-sm text-slate-400 mb-6">
        <Link to={`/projects/${projectId}`} className="hover:text-indigo-600">Project</Link>
        <span>/</span>
        <span className="text-slate-700 font-medium">Workflows</span>
      </div>

      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold text-slate-800">Workflows</h2>
        <button
          onClick={handleNew}
          disabled={createWorkflow.isPending}
          className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-60 transition-colors"
        >
          + New Workflow
        </button>
      </div>

      {isLoading && <div className="text-center py-12 text-slate-400 text-sm">Loading…</div>}

      {workflows && workflows.length === 0 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-10 text-center">
          <p className="text-sm font-medium text-slate-700">No workflows yet</p>
          <p className="text-xs text-slate-400 mt-1">Create a workflow to define your ingest pipeline</p>
        </div>
      )}

      {workflows && workflows.length > 0 && (
        <div className="space-y-2">
          {workflows.map(wf => (
            <div key={wf.id} className="flex items-center justify-between bg-white rounded-xl border border-slate-200 shadow-sm px-5 py-4">
              <Link to={`/workflows/${wf.id}`} className="flex-1 hover:text-indigo-600 transition-colors">
                <p className="font-semibold text-slate-800">{wf.name}</p>
                <p className="text-xs text-slate-400 mt-0.5">v{wf.version} · {new Date(wf.created_at).toLocaleDateString()}</p>
              </Link>
              <div className="flex items-center gap-2">
                <Link
                  to={`/workflows/${wf.id}`}
                  className="text-xs border border-slate-300 text-slate-600 px-3 py-1.5 rounded-lg hover:bg-slate-50"
                >
                  Edit
                </Link>
                <button
                  onClick={() => deleteWorkflow.mutate(wf.id)}
                  className="text-xs text-red-400 hover:text-red-600 transition-colors px-2"
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
