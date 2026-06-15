// One-click ingest workflow: a single extract_frames step whose source_id is
// resolved from the run param the confirm-upload trigger passes. Matches
// schemas/extract_frames.json (interval_seconds required). Shared by Project
// Settings and the Data Sources upload control so the two can't drift.
export const INGEST_WORKFLOW_NAME = 'Extract frames'

export const INGEST_WORKFLOW_DEFINITION = {
  steps: [
    {
      id: 'extract',
      type: 'step.extract_frames',
      config: { interval_seconds: 2 },
      inputs: { source_id: '$run.params.source_id' },
    },
  ],
  edges: [],
}
