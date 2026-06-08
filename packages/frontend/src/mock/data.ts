export const MOCK_PROJECTS = [
  {
    id: '1',
    name: 'Road Traffic Detection',
    task_type: 'detection',
    sample_count: 2450,
    dataset_count: 3,
    run_count: 12,
    model_count: 4,
    last_run_status: 'running',
    created_at: '2024-05-10',
  },
  {
    id: '2',
    name: 'Medical Scan Classification',
    task_type: 'classification',
    sample_count: 890,
    dataset_count: 1,
    run_count: 3,
    model_count: 1,
    last_run_status: 'completed',
    created_at: '2024-06-01',
  },
  {
    id: '3',
    name: 'Warehouse Defect Detection',
    task_type: 'detection',
    sample_count: 5120,
    dataset_count: 5,
    run_count: 28,
    model_count: 9,
    last_run_status: 'failed',
    created_at: '2024-03-20',
  },
]

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
    description: 'Launch Docker training container',
    accent: 'bg-red-500',
  },
]

export type RunStep = {
  id: string
  type_key: string
  label: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  started_at: string | null
  finished_at: string | null
  duration: string | null
  outputs: Record<string, string | number> | null
  logs: string | null
  cvat_url?: string
}

export const MOCK_RUN = {
  id: 'run-1',
  workflow_name: 'Main Pipeline',
  project_name: 'Road Traffic Detection',
  project_id: '1',
  status: 'running',
  started_at: '2024-06-08T10:30:00Z',
  steps: [
    {
      id: 's1',
      type_key: 'step.extract_frames',
      label: 'Extract Frames',
      status: 'completed',
      started_at: '2024-06-08T10:30:00Z',
      finished_at: '2024-06-08T10:32:14Z',
      duration: '2m 14s',
      outputs: { samples_extracted: 2450, skipped_duplicates: 12 },
      logs: 'Extracting frames from traffic_cam_01.mp4...\nExtracted 2450 frames at 2fps\nDeduplication: 12 frames skipped (identical content hash)\nDone.',
    },
    {
      id: 's2',
      type_key: 'step.auto_label',
      label: 'Auto Label',
      status: 'completed',
      started_at: '2024-06-08T10:32:15Z',
      finished_at: '2024-06-08T10:40:17Z',
      duration: '8m 02s',
      outputs: { labeled: 2450, confidence_avg: 0.87 },
      logs: 'Loading YOLOv8n checkpoint...\nRunning inference on 2450 images...\nAverage confidence: 0.87\nDetected: car (1823), truck (412), pedestrian (215)\nDone.',
    },
    {
      id: 's3',
      type_key: 'step.human_review',
      label: 'Human Review',
      status: 'running',
      started_at: '2024-06-08T10:40:18Z',
      finished_at: null,
      duration: null,
      outputs: null,
      logs: 'Creating CVAT task #47...\nUploading 2450 images...\nUploading pre-labels...\nWaiting for annotators to complete review...',
      cvat_url: 'http://cvat.local/tasks/47',
    },
    {
      id: 's4',
      type_key: 'step.commit_dataset',
      label: 'Commit Dataset',
      status: 'pending',
      started_at: null,
      finished_at: null,
      duration: null,
      outputs: null,
      logs: null,
    },
    {
      id: 's5',
      type_key: 'step.export_yolo',
      label: 'Export YOLO',
      status: 'pending',
      started_at: null,
      finished_at: null,
      duration: null,
      outputs: null,
      logs: null,
    },
    {
      id: 's6',
      type_key: 'step.train',
      label: 'Train',
      status: 'pending',
      started_at: null,
      finished_at: null,
      duration: null,
      outputs: null,
      logs: null,
    },
  ] as RunStep[],
}

export const MOCK_RECENT_RUNS = [
  { id: 'run-1', workflow_name: 'Main Pipeline', status: 'running',   started_at: '2024-06-08T10:30:00Z', step: 'Human Review' },
  { id: 'run-2', workflow_name: 'Main Pipeline', status: 'completed', started_at: '2024-06-07T09:00:00Z', step: 'Train' },
  { id: 'run-3', workflow_name: 'Quick Label',   status: 'failed',    started_at: '2024-06-06T14:22:00Z', step: 'Auto Label' },
]
