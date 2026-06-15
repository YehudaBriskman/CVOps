import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useSamples } from '../api/samples'
import { SampleGrid } from '../components/dataset/SampleGrid'

export default function SampleBrowser() {
  const { id: projectId } = useParams<{ id: string }>()
  const [params] = useSearchParams()
  const sourceId = params.get('source') ?? undefined

  const { data, isLoading, hasNextPage, isFetchingNextPage, fetchNextPage } = useSamples(projectId, sourceId)

  const totalLoaded = data?.pages.flatMap(p => p.items).length ?? 0

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center gap-2 text-sm text-slate-400 mb-6">
        <Link to={`/projects/${projectId}`} className="hover:text-indigo-600">Project</Link>
        <span>/</span>
        <span className="text-slate-700 font-medium">Samples</span>
      </div>

      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-xl font-bold text-slate-800">Samples</h2>
          {totalLoaded > 0 && <p className="text-sm text-slate-400 mt-0.5">{totalLoaded} frame{totalLoaded === 1 ? '' : 's'} loaded</p>}
        </div>
      </div>

      {sourceId && (
        <div className="flex items-center gap-2 mb-4 text-sm">
          <span className="inline-flex items-center gap-1.5 bg-indigo-50 text-indigo-700 px-3 py-1 rounded-full text-xs font-medium">
            Filtered by source {sourceId.slice(0, 8)}…
          </span>
          <Link to={`/projects/${projectId}/samples`} className="text-xs text-slate-400 hover:text-slate-600">
            Clear filter
          </Link>
        </div>
      )}

      <SampleGrid
        data={data}
        isLoading={isLoading}
        hasNextPage={hasNextPage}
        isFetchingNextPage={isFetchingNextPage}
        fetchNextPage={fetchNextPage}
      />
    </div>
  )
}
