import type { InfiniteData } from '@tanstack/react-query'
import type { CursorPage, Sample } from '../../api/samples'
import { useThumbnailUrl } from '../../api/samples'

function ThumbnailCard({ sample }: { sample: Sample }) {
  const { data } = useThumbnailUrl(sample.id)

  return (
    <div className="aspect-square rounded-lg overflow-hidden border border-slate-200 bg-slate-100 relative group">
      {data?.url ? (
        <img
          src={data.url}
          alt={`frame ${sample.frame_index ?? ''}`}
          className="w-full h-full object-cover"
          loading="lazy"
        />
      ) : (
        <div className="w-full h-full flex items-center justify-center">
          <div className="w-5 h-5 border-2 border-slate-300 border-t-slate-500 rounded-full animate-spin" />
        </div>
      )}
      <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-2">
        <p className="text-white text-xs">
          {sample.width}×{sample.height}
          {sample.frame_index != null && ` · f${sample.frame_index}`}
        </p>
      </div>
    </div>
  )
}

interface Props {
  data: InfiniteData<CursorPage<Sample>> | undefined
  isLoading: boolean
  hasNextPage: boolean
  isFetchingNextPage: boolean
  fetchNextPage: () => void
}

export function SampleGrid({ data, isLoading, hasNextPage, isFetchingNextPage, fetchNextPage }: Props) {
  const samples = data?.pages.flatMap((p: CursorPage<Sample>) => p.items) ?? []

  if (isLoading) {
    return <div className="text-center py-12 text-slate-400 text-sm">Loading…</div>
  }

  if (samples.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-10 text-center">
        <p className="text-sm font-medium text-slate-700">No samples yet</p>
        <p className="text-xs text-slate-400 mt-1">Samples are extracted from uploaded videos</p>
      </div>
    )
  }

  return (
    <div>
      <div className="grid grid-cols-4 gap-2 sm:grid-cols-6 lg:grid-cols-8">
        {samples.map(s => (
          <ThumbnailCard key={s.id} sample={s} />
        ))}
      </div>

      {hasNextPage && (
        <button
          onClick={() => fetchNextPage()}
          disabled={isFetchingNextPage}
          className="mt-4 w-full border border-slate-300 text-slate-600 py-2 rounded-lg text-sm hover:bg-slate-50 disabled:opacity-60 transition-colors"
        >
          {isFetchingNextPage ? 'Loading…' : 'Load more'}
        </button>
      )}
    </div>
  )
}
