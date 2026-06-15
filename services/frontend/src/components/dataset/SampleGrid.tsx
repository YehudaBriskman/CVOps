import { useEffect, useState } from 'react'
import type { InfiniteData } from '@tanstack/react-query'
import type { CursorPage, Sample } from '../../api/samples'
import { useImageUrl, useThumbnailUrl } from '../../api/samples'

function ThumbnailCard({ sample, onOpen }: { sample: Sample; onOpen: () => void }) {
  const { data } = useThumbnailUrl(sample.id)

  return (
    <button
      onClick={onOpen}
      className="aspect-square rounded-lg overflow-hidden border border-border bg-surface-3 relative group focus:outline-none focus:ring-2 focus:ring-focus"
    >
      {data?.url ? (
        <img
          src={data.url}
          alt={`frame ${sample.frame_index ?? ''}`}
          className="w-full h-full object-cover"
          loading="lazy"
        />
      ) : (
        <div className="w-full h-full flex items-center justify-center">
          <div className="w-5 h-5 border-2 border-border-strong border-t-text-secondary rounded-full animate-spin" />
        </div>
      )}
      <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-2">
        <p className="text-white text-xs">
          {sample.width}×{sample.height}
          {sample.frame_index != null && ` · f${sample.frame_index}`}
        </p>
      </div>
    </button>
  )
}

function Lightbox({
  samples,
  index,
  onClose,
  onNavigate,
}: {
  samples: Sample[]
  index: number
  onClose: () => void
  onNavigate: (next: number) => void
}) {
  const sample = samples[index]
  const { data, isLoading } = useImageUrl(sample?.id)

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
      if (e.key === 'ArrowRight' && index < samples.length - 1) onNavigate(index + 1)
      if (e.key === 'ArrowLeft' && index > 0) onNavigate(index - 1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [index, samples.length, onClose, onNavigate])

  if (!sample) return null

  return (
    <div
      className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-6"
      onClick={onClose}
    >
      <button
        onClick={onClose}
        className="absolute top-4 right-5 text-white/70 hover:text-white text-2xl leading-none"
        aria-label="Close"
      >
        ×
      </button>

      {index > 0 && (
        <button
          onClick={e => { e.stopPropagation(); onNavigate(index - 1) }}
          className="absolute left-4 text-white/60 hover:text-white text-4xl px-2"
          aria-label="Previous"
        >
          ‹
        </button>
      )}

      <div className="max-w-5xl max-h-[85vh] flex flex-col items-center" onClick={e => e.stopPropagation()}>
        {isLoading || !data?.url ? (
          <div className="w-10 h-10 border-2 border-white/30 border-t-white rounded-full animate-spin" />
        ) : (
          <img src={data.url} alt={`frame ${sample.frame_index ?? ''}`} className="max-h-[80vh] max-w-full object-contain rounded-lg" />
        )}
        <p className="text-white/70 text-xs mt-3">
          {sample.width}×{sample.height}
          {sample.frame_index != null && ` · frame ${sample.frame_index}`}
          {` · ${index + 1} / ${samples.length}`}
        </p>
      </div>

      {index < samples.length - 1 && (
        <button
          onClick={e => { e.stopPropagation(); onNavigate(index + 1) }}
          className="absolute right-4 text-white/60 hover:text-white text-4xl px-2"
          aria-label="Next"
        >
          ›
        </button>
      )}
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
  const [openIndex, setOpenIndex] = useState<number | null>(null)

  if (isLoading) {
    return <div className="text-center py-12 text-text-muted text-sm">Loading…</div>
  }

  if (samples.length === 0) {
    return (
      <div className="bg-surface-2 rounded-xl border border-border shadow-sm p-10 text-center">
        <p className="text-sm font-medium text-text-primary">No samples yet</p>
        <p className="text-xs text-text-muted mt-1">Samples are extracted from uploaded videos</p>
      </div>
    )
  }

  return (
    <div>
      <div className="grid grid-cols-4 gap-2 sm:grid-cols-6 lg:grid-cols-8">
        {samples.map((s, i) => (
          <ThumbnailCard key={s.id} sample={s} onOpen={() => setOpenIndex(i)} />
        ))}
      </div>

      {hasNextPage && (
        <button
          onClick={() => fetchNextPage()}
          disabled={isFetchingNextPage}
          className="mt-4 w-full border border-border-strong text-text-secondary py-2 rounded-lg text-sm hover:bg-surface-3 disabled:opacity-60 transition-colors"
        >
          {isFetchingNextPage ? 'Loading…' : 'Load more'}
        </button>
      )}

      {openIndex !== null && (
        <Lightbox
          samples={samples}
          index={openIndex}
          onClose={() => setOpenIndex(null)}
          onNavigate={setOpenIndex}
        />
      )}
    </div>
  )
}
