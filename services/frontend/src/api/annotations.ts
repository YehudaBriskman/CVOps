import { useQuery } from '@tanstack/react-query'
import { client } from '../lib/client'

/** One annotation object. coords are normalized 0..1, center-format:
 *  [cx, cy, w, h]. Mirrors export_yolo.py / worker-cvat geometry conversion. */
export interface AnnotationBox {
  class_key: string
  geometry: { coords: number[] }
}

/** The server types `payload` loosely as a dict; on the wire it is the list of
 *  annotation objects for the revision. */
export interface AnnotationRevision {
  id: string
  sample_id: string
  ontology_id: string
  ontology_version: number
  revision_no: number
  payload: AnnotationBox[]
  provenance: Record<string, unknown> | null
  created_at: string
}

export function useAnnotations(sampleId: string | undefined) {
  return useQuery<AnnotationRevision[]>({
    queryKey: ['annotations', sampleId],
    queryFn: async () => {
      const { data } = await client.get<AnnotationRevision[]>(
        `/samples/${sampleId}/annotations`,
      )
      return data
    },
    enabled: !!sampleId,
  })
}
