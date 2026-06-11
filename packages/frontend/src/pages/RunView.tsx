import { useParams, Link } from 'react-router-dom'

export default function RunView() {
  const { id } = useParams<{ id: string }>()

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-center gap-2 text-sm text-mist mb-4">
        <Link to="/projects" className="hover:text-cobalt transition-colors">Projects</Link>
        <span>/</span>
        <span className="text-slate-600 font-medium">Run {id ?? ''}</span>
      </div>

      <div className="rounded-xl border border-cloud bg-white shadow-sm p-10 text-center">
        <p className="text-sm font-medium text-ink">Run view</p>
        <p className="text-xs text-mist mt-1">
          Live status, step cards, and gate banners will appear here once the runs API is wired up.
        </p>
      </div>
    </div>
  )
}
