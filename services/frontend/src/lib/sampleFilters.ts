import type { SampleFilters } from '../api/samples'

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
