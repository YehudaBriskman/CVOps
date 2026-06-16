import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { client } from '../lib/client'

export interface Ontology {
  id: string
  project_id: string
  name: string
  version: number
  created_at: string
}

export interface LabelClass {
  id: string
  ontology_id: string
  class_key: string
  display_name: string
  color: string
  sort_order: number
}

export function useOntologies(projectId: string | undefined) {
  return useQuery<Ontology[]>({
    queryKey: ['ontologies', projectId],
    queryFn: async () => {
      const { data } = await client.get<Ontology[]>(`/projects/${projectId}/ontologies`)
      return data
    },
    enabled: !!projectId,
  })
}

export function useCreateOntology(projectId: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { name: string }) => {
      const { data } = await client.post<Ontology>(`/projects/${projectId}/ontologies`, body)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ontologies', projectId] }),
  })
}

export function useLabelClasses(ontologyId: string | undefined) {
  return useQuery<LabelClass[]>({
    queryKey: ['label-classes', ontologyId],
    queryFn: async () => {
      const { data } = await client.get<LabelClass[]>(`/ontologies/${ontologyId}/classes`)
      return data
    },
    enabled: !!ontologyId,
  })
}

export function useCreateLabelClass(ontologyId: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: {
      class_key: string
      display_name: string
      color: string
      sort_order: number
    }) => {
      const { data } = await client.post<LabelClass>(`/ontologies/${ontologyId}/classes`, body)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['label-classes', ontologyId] }),
  })
}

export function useDeleteLabelClass(ontologyId: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (classId: string) => {
      await client.delete(`/ontologies/${ontologyId}/classes/${classId}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['label-classes', ontologyId] }),
  })
}
