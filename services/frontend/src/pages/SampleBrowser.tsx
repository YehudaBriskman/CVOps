import { useEffect, useMemo, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { useSamples } from '../api/samples'
import type { Sample } from '../api/samples'
import { SampleGrid } from '../components/dataset/SampleGrid'
import { SampleFilterBar, parseSampleFilters } from '../components/samples/SampleFilterBar'
import { BulkActionBar } from '../components/samples/BulkActionBar'
import { SampleEditDrawer } from '../components/samples/SampleEditDrawer'
import { useSelectionStore } from '../store/selection'
import { Breadcrumbs, ErrorState } from '../components/ui'

export default function SampleBrowser() {
  const { id: projectId } = useParams<{ id: string }>()
  const [params] = useSearchParams()
  const filters = useMemo(() => parseSampleFilters(params), [params])
  const filterKey = params.toString()

  const { data, isLoading, isError, refetch, hasNextPage, isFetchingNextPage, fetchNextPage } =
    useSamples(projectId, filters)

  const clear = useSelectionStore((s) => s.clear)
  const [editId, setEditId] = useState<string | null>(null)

  // Drop the selection whenever the active filters change — selected ids from a
  // previous view would otherwise leak into bulk actions.
  useEffect(() => {
    clear()
  }, [filterKey, clear])

  // Also clear on unmount so a selection can't leak into another view.
  useEffect(() => () => clear(), [clear])

  const samples = data?.pages.flatMap((p) => p.items) ?? []
  const editSample: Sample | null = samples.find((s) => s.id === editId) ?? null
  const totalLoaded = samples.length

  return (
    <div className="mx-auto max-w-7xl p-6 pb-24">
      <Breadcrumbs items={[{ label: 'Project', to: `/projects/${projectId}` }, { label: 'Samples' }]} />

      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-text-primary">Samples</h2>
          {totalLoaded > 0 && (
            <p className="mt-0.5 text-sm text-text-muted">
              {totalLoaded} frame{totalLoaded === 1 ? '' : 's'} loaded
            </p>
          )}
        </div>
      </div>

      {projectId && <SampleFilterBar projectId={projectId} />}

      {isError ? (
        <ErrorState description="Could not load samples." onRetry={() => refetch()} />
      ) : (
        <SampleGrid
          data={data}
          isLoading={isLoading}
          hasNextPage={hasNextPage}
          isFetchingNextPage={isFetchingNextPage}
          fetchNextPage={fetchNextPage}
          selectable
          projectId={projectId}
          onEdit={(s) => setEditId(s.id)}
        />
      )}

      {projectId && <BulkActionBar projectId={projectId} onEdit={setEditId} />}
      {projectId && (
        <SampleEditDrawer projectId={projectId} sample={editSample} onClose={() => setEditId(null)} />
      )}
    </div>
  )
}
