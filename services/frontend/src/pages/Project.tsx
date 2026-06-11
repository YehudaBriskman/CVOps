import { useParams, Link } from 'react-router-dom'

export default function Project() {
  const { id } = useParams<{ id: string }>()

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center gap-2 text-sm text-mist mb-6">
        <Link to="/projects" className="hover:text-cobalt transition-colors">Projects</Link>
        <span>/</span>
        <span className="text-slate-600 font-medium">{id ?? 'Unknown'}</span>
      </div>

      <div className="rounded-xl border border-cloud bg-white shadow-sm p-10 text-center">
        <p className="text-sm font-medium text-ink">Project view</p>
        <p className="text-xs text-mist mt-1">
          Stats, recent runs, and actions will appear here once the API is wired up.
        </p>
      </div>
    </div>
  )
}
