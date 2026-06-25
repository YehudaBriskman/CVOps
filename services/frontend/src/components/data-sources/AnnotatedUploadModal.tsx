import { useRef, useState } from 'react'
import { useOntologies } from '../../api/ontologies'
import { useUploadAnnotatedImages } from '../../api/data-sources'
import { parseYoloLabel, parseClassFile, stem } from '../../lib/yolo'
import type { AnnotatedImagePair } from '../../api/data-sources'

interface Props {
  projectId: string
  onClose: () => void
  onDone: (result: { created: number; annotated: number }) => void
}

interface ValidationIssue {
  filename: string
  message: string
}

interface UploadSummary {
  pairs: AnnotatedImagePair[]
  classNames: string[]
  imageCount: number
  boxCount: number
  issues: ValidationIssue[]
}

const IMAGE_EXTS = new Set(['jpg', 'jpeg', 'png', 'bmp', 'webp', 'tif', 'tiff'])

function isImage(f: File) {
  const ext = f.name.split('.').pop()?.toLowerCase() ?? ''
  return IMAGE_EXTS.has(ext) || f.type.startsWith('image/')
}

function isLabel(f: File) {
  return f.name.toLowerCase().endsWith('.txt') && !f.name.toLowerCase().endsWith('classes.txt')
}

function isClassFile(f: File) {
  const lower = f.name.toLowerCase()
  return lower === 'classes.txt' || lower.endsWith('data.yaml') || lower.endsWith('data.yml')
}

async function readText(f: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = () => reject(reader.error)
    reader.readAsText(f)
  })
}

async function buildSummary(
  imageFiles: File[],
  labelFiles: File[],
  classNames: string[],
): Promise<UploadSummary> {
  const labelByBase = new Map<string, File>()
  for (const f of labelFiles) labelByBase.set(stem(f.name), f)

  const pairs: AnnotatedImagePair[] = []
  const issues: ValidationIssue[] = []
  let boxCount = 0

  for (const img of imageFiles) {
    const base = stem(img.name)
    const labelFile = labelByBase.get(base)
    let boxes: ReturnType<typeof parseYoloLabel> = []

    if (labelFile) {
      const text = await readText(labelFile)
      boxes = parseYoloLabel(text)
      boxCount += boxes.length
      labelByBase.delete(base)
    }
    pairs.push({ image: img, boxes })
  }

  // Any remaining label files have no matching image
  for (const [base] of labelByBase) {
    issues.push({ filename: `${base}.txt`, message: 'No matching image found' })
  }

  return { pairs, classNames, imageCount: imageFiles.length, boxCount, issues }
}

export function AnnotatedUploadModal({ projectId, onClose, onDone }: Props) {
  const { data: ontologies } = useOntologies(projectId)
  const upload = useUploadAnnotatedImages(projectId)

  const imageInputRef = useRef<HTMLInputElement>(null)
  const labelInputRef = useRef<HTMLInputElement>(null)
  const classInputRef = useRef<HTMLInputElement>(null)

  const [imageFiles, setImageFiles] = useState<File[]>([])
  const [labelFiles, setLabelFiles] = useState<File[]>([])
  const [classNames, setClassNames] = useState<string[]>([])
  const [classFileName, setClassFileName] = useState<string>('')
  const [classError, setClassError] = useState<string | null>(null)
  const [ontologyId, setOntologyId] = useState<string>('')
  const [summary, setSummary] = useState<UploadSummary | null>(null)
  const [building, setBuilding] = useState(false)

  async function handleClassFile(f: File) {
    setClassError(null)
    const text = await readText(f)
    const names = parseClassFile(f.name, text)
    if (!names || names.length === 0) {
      setClassError(`Could not parse class names from ${f.name}`)
      return
    }
    setClassNames(names)
    setClassFileName(f.name)
    setSummary(null)
  }

  async function handlePreview() {
    if (imageFiles.length === 0) return
    setBuilding(true)
    try {
      const s = await buildSummary(imageFiles, labelFiles, classNames)
      setSummary(s)
    } finally {
      setBuilding(false)
    }
  }

  async function handleUpload() {
    if (!summary || summary.pairs.length === 0) return
    try {
      const result = await upload.mutateAsync({
        pairs: summary.pairs,
        classNames: summary.classNames,
        ontologyId: ontologyId || undefined,
        group: `YOLO import ${new Date().toLocaleDateString()}`,
      })
      onDone({ created: result.created, annotated: result.annotated })
    } catch {
      // error shown via upload.error below
    }
  }

  const canPreview = imageFiles.length > 0 && classNames.length > 0
  const canUpload = summary !== null && summary.imageCount > 0 && !upload.isPending

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
      <div className="bg-surface-2 rounded-xl border border-border shadow-xl w-full max-w-lg flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border flex-shrink-0">
          <h2 className="text-base font-semibold text-text-primary">Upload labeled data (YOLO)</h2>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary transition-colors">✕</button>
        </div>

        <div className="overflow-y-auto px-6 py-4 space-y-4 flex-1">
          {/* Step 1: Class file */}
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1">
              1. Class file <span className="text-text-muted font-normal">(classes.txt or data.yaml)</span>
            </label>
            <label className="flex items-center gap-3 cursor-pointer border border-dashed border-border-strong rounded-lg px-4 py-3 hover:bg-surface-3 transition-colors">
              <span className="text-sm text-text-secondary">
                {classFileName ? classFileName : 'Choose classes.txt or data.yaml'}
              </span>
              <input
                ref={classInputRef}
                type="file"
                accept=".txt,.yaml,.yml"
                className="hidden"
                onChange={e => {
                  const f = e.target.files?.[0]
                  if (f) handleClassFile(f)
                }}
              />
              <span className="ml-auto text-xs text-iris-400 shrink-0">Browse</span>
            </label>
            {classError && <p className="text-xs text-error mt-1">{classError}</p>}
            {classNames.length > 0 && (
              <p className="text-xs text-success mt-1">
                ✓ {classNames.length} classes: {classNames.slice(0, 5).join(', ')}{classNames.length > 5 ? ` +${classNames.length - 5} more` : ''}
              </p>
            )}
          </div>

          {/* Step 2: Images */}
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1">
              2. Images <span className="text-text-muted font-normal">(jpg, png, …)</span>
            </label>
            <label className="flex items-center gap-3 cursor-pointer border border-dashed border-border-strong rounded-lg px-4 py-3 hover:bg-surface-3 transition-colors">
              <span className="text-sm text-text-secondary">
                {imageFiles.length > 0 ? `${imageFiles.length} image${imageFiles.length === 1 ? '' : 's'} selected` : 'Choose image files'}
              </span>
              <input
                ref={imageInputRef}
                type="file"
                accept="image/*"
                multiple
                className="hidden"
                onChange={e => {
                  const files = Array.from(e.target.files ?? []).filter(isImage)
                  setImageFiles(files)
                  setSummary(null)
                }}
              />
              <span className="ml-auto text-xs text-iris-400 shrink-0">Browse</span>
            </label>
          </div>

          {/* Step 3: Label files */}
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1">
              3. Label files <span className="text-text-muted font-normal">(.txt, optional — images without labels get 0 boxes)</span>
            </label>
            <label className="flex items-center gap-3 cursor-pointer border border-dashed border-border-strong rounded-lg px-4 py-3 hover:bg-surface-3 transition-colors">
              <span className="text-sm text-text-secondary">
                {labelFiles.length > 0 ? `${labelFiles.length} label file${labelFiles.length === 1 ? '' : 's'} selected` : 'Choose .txt label files'}
              </span>
              <input
                ref={labelInputRef}
                type="file"
                accept=".txt"
                multiple
                className="hidden"
                onChange={e => {
                  const files = Array.from(e.target.files ?? []).filter(f => isLabel(f) && !isClassFile(f))
                  setLabelFiles(files)
                  setSummary(null)
                }}
              />
              <span className="ml-auto text-xs text-iris-400 shrink-0">Browse</span>
            </label>
          </div>

          {/* Ontology selector */}
          {ontologies && ontologies.length > 0 && (
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1">
                Ontology <span className="text-text-muted font-normal">(defaults to project ontology)</span>
              </label>
              <select
                value={ontologyId}
                onChange={e => setOntologyId(e.target.value)}
                className="w-full border border-border-strong bg-surface-1 rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-iris"
              >
                <option value="">Project default</option>
                {ontologies.map(o => (
                  <option key={o.id} value={o.id}>{o.name}</option>
                ))}
              </select>
            </div>
          )}

          {/* Preview button */}
          <button
            onClick={handlePreview}
            disabled={!canPreview || building}
            className="w-full border border-border-strong text-text-primary py-2 rounded-lg text-sm font-medium hover:bg-surface-3 disabled:opacity-50 transition-colors"
          >
            {building ? 'Pairing files…' : 'Preview summary'}
          </button>

          {/* Summary */}
          {summary && (
            <div className="bg-surface-1 rounded-lg border border-border p-4 space-y-3">
              <div className="grid grid-cols-3 gap-3 text-center">
                <div>
                  <p className="text-xl font-bold text-text-primary">{summary.imageCount}</p>
                  <p className="text-xs text-text-muted">images</p>
                </div>
                <div>
                  <p className="text-xl font-bold text-text-primary">{summary.boxCount}</p>
                  <p className="text-xs text-text-muted">boxes</p>
                </div>
                <div>
                  <p className="text-xl font-bold text-text-primary">{summary.classNames.length}</p>
                  <p className="text-xs text-text-muted">classes</p>
                </div>
              </div>

              {summary.issues.length > 0 && (
                <div className="bg-warning/5 border border-warning/30 rounded-lg p-3">
                  <p className="text-xs font-semibold text-warning mb-1">
                    {summary.issues.length} validation issue{summary.issues.length === 1 ? '' : 's'}
                  </p>
                  <ul className="space-y-0.5">
                    {summary.issues.slice(0, 5).map((issue, i) => (
                      <li key={i} className="text-xs text-text-secondary">
                        <span className="font-mono">{issue.filename}</span> — {issue.message}
                      </li>
                    ))}
                    {summary.issues.length > 5 && (
                      <li className="text-xs text-text-muted">+{summary.issues.length - 5} more</li>
                    )}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Upload error */}
          {upload.isError && (
            <p className="text-xs text-error bg-error/5 border border-error/20 rounded-lg px-3 py-2">
              {upload.error instanceof Error ? upload.error.message : 'Upload failed'}
            </p>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-border flex-shrink-0">
          <button
            onClick={onClose}
            disabled={upload.isPending}
            className="text-sm text-text-secondary hover:text-text-primary px-4 py-2 rounded-lg border border-border-strong disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleUpload}
            disabled={!canUpload}
            className="text-sm font-medium text-white bg-iris hover:bg-iris-hover px-5 py-2 rounded-lg disabled:opacity-50 transition-colors"
          >
            {upload.isPending
              ? 'Uploading…'
              : summary
              ? `Upload ${summary.imageCount} image${summary.imageCount === 1 ? '' : 's'}`
              : 'Upload'}
          </button>
        </div>
      </div>
    </div>
  )
}
