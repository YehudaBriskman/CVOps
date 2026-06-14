import { useQuery } from '@tanstack/react-query'
import { client } from '../lib/client'

export interface TrainingContainer {
  id: string
  project_id: string
  image: string
  status: string
  run_id: string | null
  created_at: string
}

export function useTrainingContainers(projectId: string | undefined) {
  return useQuery<TrainingContainer[]>({
    queryKey: ['training-containers', projectId],
    queryFn: async () => {
      const { data } = await client.get<TrainingContainer[]>(
        `/projects/${projectId}/training-containers`,
      )
      return data
    },
    enabled: !!projectId,
  })
}
