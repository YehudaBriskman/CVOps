import { useQuery } from '@tanstack/react-query'
import { client } from '../lib/client'

export interface RegistryType {
  type_key: string
  category: string
  json_schema: Record<string, unknown>
  ui_hints: {
    group?: string
    icon?: string
    description?: string
    order?: number
    [key: string]: unknown
  }
}

export function useRegistryTypes(category?: string) {
  return useQuery<RegistryType[]>({
    queryKey: ['registry-types', category],
    queryFn: async () => {
      const params = category ? `?category=${category}` : ''
      const { data } = await client.get<RegistryType[]>(`/registry/types${params}`)
      return data
    },
    staleTime: 10 * 60 * 1000,
  })
}
