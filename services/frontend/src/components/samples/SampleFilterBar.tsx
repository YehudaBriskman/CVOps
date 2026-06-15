import { useSearchParams } from 'react-router-dom'
import type { SampleFilters } from '../../api/samples'
import { useDataSources } from '../../api/data-sources'
import { useCollections } from '../../api/collections'
import { useTags } from '../../api/tags'
import { Select } from '../ui'

/** Parse the active sample filters out of the URL search params. */
export function parseSampleFilters(params: URLSearchParams): SampleFilters {
  const f: SampleFilters = {}
  const source = params.get('source_id')
  if (source) f.source_id = source
  if (params.get('review_status')) f.review_status = params.get('review_status') ?? undefined
  const ann = params.get('annotation')
  if (ann === 'with') f.has_annotations = true
  else if (ann === 'without') f.has_annotations = false
  if (params.get('collection_id')) f.collection_id = params.get('collection_id') ?? undefined
  if (params.get('tag_id')) f.tag_id = params.get('tag_id') ?? undefined
  if (params.get('created_after')) f.created_after = params.get('created_after') ?? undefined
  if (params.get('created_before')) f.created_before = params.get('created_before') ?? undefined
  return f
}

export function SampleFilterBar({ projectId }: { projectId: string }) {
  const [params, setParams] = useSearchParams()
  const { data: sources } = useDataSources(projectId)
  const collectionsQuery = useCollections(projectId)
  const { data: tags } = useTags(projectId)

  const collections = collectionsQuery.data?.pages.flatMap((p) => p.items) ?? []

  function setParam(key: string, value: string) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  const hasAny = ['source_id', 'review_status', 'annotation', 'collection_id', 'tag_id', 'created_after', 'created_before'].some(
    (k) => params.get(k),
  )

  return (
    <div className="mb-4 flex flex-wrap items-center gap-2">
      <Select
        className="w-auto"
        value={params.get('source_id') ?? ''}
        onChange={(e) => setParam('source_id', e.target.value)}
        aria-label="Filter by source"
      >
        <option value="">All sources</option>
        {sources?.map((s) => (
          <option key={s.id} value={s.id}>
            {s.type} · {s.id.slice(0, 8)}
          </option>
        ))}
      </Select>

      <Select
        className="w-auto"
        value={params.get('review_status') ?? ''}
        onChange={(e) => setParam('review_status', e.target.value)}
        aria-label="Filter by review status"
      >
        <option value="">Any review status</option>
        <option value="unreviewed">Unreviewed</option>
        <option value="accepted">Accepted</option>
        <option value="rejected">Rejected</option>
      </Select>

      <Select
        className="w-auto"
        value={params.get('annotation') ?? ''}
        onChange={(e) => setParam('annotation', e.target.value)}
        aria-label="Filter by annotation state"
      >
        <option value="">Any annotation</option>
        <option value="with">Annotated</option>
        <option value="without">Unannotated</option>
      </Select>

      <Select
        className="w-auto"
        value={params.get('collection_id') ?? ''}
        onChange={(e) => setParam('collection_id', e.target.value)}
        aria-label="Filter by collection"
      >
        <option value="">Any collection</option>
        {collections.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </Select>

      <Select
        className="w-auto"
        value={params.get('tag_id') ?? ''}
        onChange={(e) => setParam('tag_id', e.target.value)}
        aria-label="Filter by tag"
      >
        <option value="">Any tag</option>
        {tags?.map((t) => (
          <option key={t.id} value={t.id}>
            {t.name}
          </option>
        ))}
      </Select>

      {hasAny && (
        <button
          type="button"
          onClick={() => setParams(new URLSearchParams(), { replace: true })}
          className="text-xs text-text-muted underline hover:text-text-secondary"
        >
          Clear filters
        </button>
      )}
    </div>
  )
}
