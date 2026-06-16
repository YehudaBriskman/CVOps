import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useCommitSamples, type Commit } from '../../api/datasets'
import { useDataSources } from '../../api/data-sources'
import { useThumbnailUrl, type Sample } from '../../api/samples'
import { cn } from '../../lib/cn'
import { Button, Select } from '../ui'
import { CommitStats } from './CommitStats'
import { Lightbox } from './SampleGrid'

type GroupKey = 'source' | 'review' | 'annotation' | 'none'

const GROUP_OPTIONS: { value: GroupKey; label: string }[] = [
  { value: 'source', label: 'Group by source' },
  { value: 'review', label: 'Group by review status' },
  { value: 'annotation', label: 'Group by annotation' },
  { value: 'none', label: 'No grouping' },
]

function CommitThumb({ sample, onOpen }: { sample: Sample; onOpen: () => void }) {
  const { data } = useThumbnailUrl(sample.id)
  return (
    <button
      type="button"
      onClick={onOpen}
      onContextMenu={(e) => {
        e.preventDefault()
        onOpen()
      }}
      aria-label={`Open frame ${sample.frame_index ?? ''}`}
      className="group relative aspect-square overflow-hidden rounded-md border border-border bg-surface-3 transition-shadow hover:border-border-strong focus:outline-none focus:ring-2 focus:ring-focus"
    >
      {data?.url ? (
        <img src={data.url} alt={`frame ${sample.frame_index ?? ''}`} className="h-full w-full object-cover" loading="lazy" />
      ) : (
        <div className="flex h-full w-full items-center justify-center">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-border-strong border-t-text-secondary" />
        </div>
      )}
    </button>
  )
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      className={cn('h-4 w-4 transition-transform', open ? 'rotate-90' : '')}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="m9 18 6-6-6-6" />
    </svg>
  )
}

export function CommitContents({
  datasetId,
  commitId,
  projectId,
  commit,
}: {
  datasetId: string
  commitId: string
  projectId: string
  commit: Commit | undefined
}) {
  const q = useCommitSamples(datasetId, commitId)
  const { data: sources } = useDataSources(projectId)
  const [groupBy, setGroupBy] = useState<GroupKey>('source')
  const [openIndex, setOpenIndex] = useState<number | null>(null)
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())

  const samples = useMemo(() => q.data?.pages.flatMap((p) => p.items) ?? [], [q.data])

  // source_id → friendly label, so "source" folders read as names not UUIDs.
  const sourceLabel = useMemo(() => {
    const m = new Map<string, string>()
    for (const s of sources ?? []) {
      const name = typeof s.metadata?.name === 'string' ? s.metadata.name : `${s.type} · ${s.id.slice(0, 8)}`
      m.set(s.id, name)
    }
    return m
  }, [sources])

  // Partition the loaded samples into folders, keeping each sample's global
  // index so the lightbox can navigate the whole commit as one flat list.
  const folders = useMemo(() => {
    const map = new Map<string, number[]>()
    samples.forEach((s, i) => {
      let key: string
      switch (groupBy) {
        case 'source':
          key = sourceLabel.get(s.source_id) ?? `Source ${s.source_id.slice(0, 8)}`
          break
        case 'review':
          key = s.review_status
          break
        case 'annotation':
          key = s.has_annotations ? 'Annotated' : 'Unannotated'
          break
        default:
          key = 'All samples'
      }
      const arr = map.get(key)
      if (arr) arr.push(i)
      else map.set(key, [i])
    })
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]))
  }, [samples, groupBy, sourceLabel])

  function toggleFolder(key: string) {
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  return (
    <section className="min-w-0">
      {/* Header */}
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-base font-semibold text-text-primary">{commit?.message ?? 'Commit'}</h3>
          <p className="mt-0.5 text-xs text-text-muted">
            <span className="font-mono">{commitId.slice(0, 10)}</span>
            {commit && ` · ${new Date(commit.created_at).toLocaleString()}`}
            {samples.length > 0 && ` · ${samples.length} loaded`}
          </p>
        </div>
        <Link to={`/datasets/${datasetId}/commits/${commitId}`} className="shrink-0">
          <Button size="sm" variant="secondary">
            Open detail
          </Button>
        </Link>
      </div>

      {commit?.stats && (
        <div className="mb-4">
          <CommitStats stats={commit.stats} />
        </div>
      )}

      <div className="mb-3 flex items-center justify-between gap-3">
        <Select
          className="w-auto"
          value={groupBy}
          onChange={(e) => setGroupBy(e.target.value as GroupKey)}
          aria-label="Group commit samples"
        >
          {GROUP_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </Select>
        <span className="text-xs text-text-muted">{folders.length} folder{folders.length === 1 ? '' : 's'}</span>
      </div>

      {q.isLoading ? (
        <div className="py-12 text-center text-sm text-text-muted">Loading samples…</div>
      ) : samples.length === 0 ? (
        <div className="rounded-xl border border-border bg-surface-2 p-10 text-center shadow-sm">
          <p className="text-sm font-medium text-text-primary">No samples in this commit</p>
        </div>
      ) : (
        <div className="space-y-3">
          {folders.map(([label, indices]) => {
            const open = !collapsed.has(label)
            return (
              <div key={label} className="overflow-hidden rounded-xl border border-border bg-surface-2">
                <button
                  type="button"
                  onClick={() => toggleFolder(label)}
                  aria-expanded={open}
                  className="flex w-full items-center gap-2 px-4 py-2.5 text-left hover:bg-surface-3"
                >
                  <Chevron open={open} />
                  <span className="truncate text-sm font-medium text-text-primary">{label}</span>
                  <span className="ml-auto rounded-full bg-surface-3 px-2 py-0.5 text-xs text-text-muted">
                    {indices.length}
                  </span>
                </button>
                {open && (
                  <div className="grid grid-cols-3 gap-2 px-4 pb-4 sm:grid-cols-5 lg:grid-cols-6">
                    {indices.map((gi) => (
                      <CommitThumb key={samples[gi].id} sample={samples[gi]} onOpen={() => setOpenIndex(gi)} />
                    ))}
                  </div>
                )}
              </div>
            )
          })}

          {q.hasNextPage && (
            <Button
              variant="secondary"
              className="w-full"
              loading={q.isFetchingNextPage}
              onClick={() => q.fetchNextPage()}
            >
              Load more samples
            </Button>
          )}
        </div>
      )}

      {openIndex !== null && (
        <Lightbox
          samples={samples}
          index={openIndex}
          onClose={() => setOpenIndex(null)}
          onNavigate={setOpenIndex}
        />
      )}
    </section>
  )
}
