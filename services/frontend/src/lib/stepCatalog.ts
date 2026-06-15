export type StepTypeDef = {
  type_key: string
  label: string
  description: string
  accent: string
}

export const STEP_TYPES: StepTypeDef[] = [
  {
    type_key: 'step.extract_frames',
    label: 'Extract Frames',
    description: 'Extract frames from video at configured FPS',
    accent: 'bg-blue-500',
  },
  {
    type_key: 'step.auto_label',
    label: 'Auto Label',
    description: 'Run inference model to pre-label images',
    accent: 'bg-purple-500',
  },
  {
    type_key: 'step.human_review',
    label: 'Human Review',
    description: 'Push to CVAT for human annotation',
    accent: 'bg-orange-500',
  },
  {
    type_key: 'step.commit_dataset',
    label: 'Commit Dataset',
    description: 'Snapshot labeled data immutably',
    accent: 'bg-green-600',
  },
  {
    type_key: 'step.export_yolo',
    label: 'Export YOLO',
    description: 'Materialize dataset to YOLO format',
    accent: 'bg-yellow-500',
  },
  {
    type_key: 'step.train',
    label: 'Train',
    description: 'Clone a trainer repo and run it on the exported dataset',
    accent: 'bg-red-500',
  },
]
