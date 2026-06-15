import { useEffect, useState } from 'react'
import type { InfiniteData } from '@tanstack/react-query'
import type { CursorPage, Sample } from '../../api/samples'
import { useImageUrl, useThumbnailUrl } from '../../api/samples'
import { useSelectionStore } from '../../store/selection'
import { cn } from '../../lib/cn'

const REVIEW_DOT: Record<string, string> = {
  accepted: '#34D399',
  rejected: '#FB7185',
  unreviewed: 'var(--text-muted)',
}

function ThumbnailCard({
  sample,
  onOpen,
  selectable,
  selected,
  onToggle,
}: {
  sample: Sample
  onOpen: () => void
  selectable: boolean
  selected: boolean
  onToggle: () => void
}) {
  const { data } = useThumbnailUrl(sample.id)

  return (
    <div
      className={cn(
        'group relative aspect-square overflow-hidden rounded-lg border bg-surface-3',
        selected ? 'border-iris ring-2 ring-iris' : 'border-border',
      )}
    >
      <button
        onClick={onOpen}
        className="h-full w-full focus:outline-none focus:ring-2 focus:ring-focus"
        aria-label={`Open frame ${sample.frame_index ?? ''}`}
      >
        {data?.url ? (
          <img
            src={data.url}
            alt={`frame ${sample.frame_index ?? ''}`}
            className="h-full w-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-border-strong border-t-text-secondary" />
          </div>
        )}
      </button>

      {selectable && (
        <button
          type="button"
          onClick={onToggle}
          aria-label={selected ? 'Deselect' : 'Select'}
          aria-pressed={selected}
          className={cn(
            'absolute left-1.5 top-1.5 flex h-5 w-5 items-center justify-center rounded border text-[10px] font-bold transition-opacity',
            selected
              ? 'border-iris bg-iris text-white opacity-100'
              : 'border-white/70 bg-black/40 text-transparent opacity-0 group-hover:opacity-100',
          )}
        >
          ✓
        </button>
      )}

      {/* Status + tag indicators */}
      <div className="pointer-events-none absolute right-1.5 top-1.5 flex items-center gap-1">
        {sample.tags.slice(0, 3).map((t) => (
          <span
            key={t.id}
            className="h-2 w-2 rounded-full ring-1 ring-black/30"
            style={{ backgroundColor: t.color }}
            title={t.name}
          />
        ))}
        <span
          className="h-2 w-2 rounded-full ring-1 ring-black/30"
          style={{ backgroundColor: REVIEW_DOT[sample.review_status] ?? 'var(--text-muted)' }}
          title={sample.review_status}
        />
      </div>

      <div className="pointer-events-none absolute inset-x-0 bottom-0 flex items-end bg-gradient-to-t from-black/60 to-transparent p-2 opacity-0 transition-opacity group-hover:opacity-100">
        <p className="text-xs text-white">
          {sample.width}×{sample.height}
          {sample.frame_index != null && ` · f${sample.frame_index}`}
        </p>
      </div>
    </div>
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-6" onClick={onClose}>
      <button
        onClick={onClose}
        className="absolute right-5 top-4 text-2xl leading-none text-white/70 hover:text-white"
        aria-label="Close"
      >
        ×
      </button>

      {index > 0 && (
        <button
          onClick={(e) => {
            e.stopPropagation()
            onNavigate(index - 1)
          }}
          className="absolute left-4 px-2 text-4xl text-white/60 hover:text-white"
          aria-label="Previous"
        >
          ‹
        </button>
      )}

      <div className="flex max-h-[85vh] max-w-5xl flex-col items-center" onClick={(e) => e.stopPropagation()}>
        {isLoading || !data?.url ? (
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-white/30 border-t-white" />
        ) : (
          <img
            src={data.url}
            alt={`frame ${sample.frame_index ?? ''}`}
            className="max-h-[80vh] max-w-full rounded-lg object-contain"
          />
        )}
        <p className="mt-3 text-xs text-white/70">
          {sample.width}×{sample.height}
          {sample.frame_index != null && ` · frame ${sample.frame_index}`}
          {` · ${index + 1} / ${samples.length}`}
        </p>
      </div>

      {index < samples.length - 1 && (
        <button
          onClick={(e) => {
            e.stopPropagation()
            onNavigate(index + 1)
          }}
          className="absolute right-4 px-2 text-4xl text-white/60 hover:text-white"
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
  selectable?: boolean
}

export function SampleGrid({
  data,
  isLoading,
  hasNextPage,
  isFetchingNextPage,
  fetchNextPage,
  selectable = false,
}: Props) {
  const samples = data?.pages.flatMap((p: CursorPage<Sample>) => p.items) ?? []
  const [openIndex, setOpenIndex] = useState<number | null>(null)
  const selected = useSelectionStore((s) => s.selected)
  const toggle = useSelectionStore((s) => s.toggle)
  const add = useSelectionStore((s) => s.add)
  const clear = useSelectionStore((s) => s.clear)

  if (isLoading) {
    return <div className="py-12 text-center text-sm text-text-muted">Loading…</div>
  }

  if (samples.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-surface-2 p-10 text-center shadow-sm">
        <p className="text-sm font-medium text-text-primary">No samples yet</p>
        <p className="mt-1 text-xs text-text-muted">Samples are extracted from uploaded videos</p>
      </div>
    )
  }

  const pageIds = samples.map((s) => s.id)
  const allSelected = pageIds.every((id) => selected.has(id))

  return (
    <div>
      {selectable && (
        <div className="mb-2 flex items-center gap-3 text-xs text-text-muted">
          <button
            type="button"
            onClick={() => (allSelected ? clear() : add(pageIds))}
            className="underline hover:text-text-secondary"
          >
            {allSelected ? 'Deselect all' : 'Select all on page'}
          </button>
          <span>{selected.size} selected</span>
        </div>
      )}

      <div className="grid grid-cols-4 gap-2 sm:grid-cols-6 lg:grid-cols-8">
        {samples.map((s, i) => (
          <ThumbnailCard
            key={s.id}
            sample={s}
            onOpen={() => setOpenIndex(i)}
            selectable={selectable}
            selected={selected.has(s.id)}
            onToggle={() => toggle(s.id)}
          />
        ))}
      </div>

      {hasNextPage && (
        <button
          onClick={() => fetchNextPage()}
          disabled={isFetchingNextPage}
          className="mt-4 w-full rounded-lg border border-border-strong py-2 text-sm text-text-secondary transition-colors hover:bg-surface-3 disabled:opacity-60"
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
