/** A parsed YOLO bounding box from a .txt label file. */
export interface YoloBox {
  class_id: number
  cx: number
  cy: number
  w: number
  h: number
  confidence: number | null
}

/**
 * Parse a single YOLO .txt label file into boxes.
 * Each line: `<class_id> <cx> <cy> <w> <h> [conf]` (values normalized 0–1).
 * Blank lines and malformed lines are silently skipped.
 */
export function parseYoloLabel(text: string): YoloBox[] {
  const boxes: YoloBox[] = []
  for (const rawLine of text.split('\n')) {
    const line = rawLine.trim()
    if (!line) continue
    const parts = line.split(/\s+/)
    if (parts.length < 5) continue
    const [classId, cx, cy, w, h, conf] = parts.map(Number)
    if ([classId, cx, cy, w, h].some(isNaN)) continue
    boxes.push({
      class_id: Math.round(classId),
      cx,
      cy,
      w,
      h,
      confidence: parts[5] !== undefined && !isNaN(conf) ? conf : null,
    })
  }
  return boxes
}

/**
 * Parse a `classes.txt` file (one class name per line) into an ordered array.
 */
export function parseClassesTxt(text: string): string[] {
  return text
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)
}

/**
 * Parse a `data.yaml` file and extract the `names` field.
 * Supports both inline list `names: [a, b]` and block list:
 *   names:
 *     - a
 *     - b
 * Returns null if the field is not found.
 */
export function parseDataYaml(text: string): string[] | null {
  // Inline: names: [car, person, bike]
  const inline = text.match(/^names\s*:\s*\[([^\]]+)\]/m)
  if (inline) {
    return inline[1]
      .split(',')
      .map((s) => s.trim().replace(/^['"]|['"]$/g, ''))
      .filter(Boolean)
  }

  // Block list:
  // names:
  //   - car
  //   - person
  const blockSection = text.match(/^names\s*:\s*\n((?:[ \t]+-[^\n]+\n?)+)/m)
  if (blockSection) {
    return blockSection[1]
      .split('\n')
      .map((l) => l.replace(/^\s*-\s*/, '').trim().replace(/^['"]|['"]$/g, ''))
      .filter(Boolean)
  }

  return null
}

/**
 * Dispatch to the right parser based on filename.
 * Returns null when the format is unrecognised or parsing fails.
 */
export function parseClassFile(filename: string, text: string): string[] | null {
  const lower = filename.toLowerCase()
  if (lower.endsWith('.yaml') || lower.endsWith('.yml')) {
    return parseDataYaml(text)
  }
  if (lower === 'classes.txt' || lower.endsWith('/classes.txt')) {
    return parseClassesTxt(text)
  }
  // Fallback: try plain line-per-class format for any other .txt
  if (lower.endsWith('.txt')) {
    const result = parseClassesTxt(text)
    return result.length > 0 ? result : null
  }
  return null
}

/** Strip extension from a filename basename (e.g. "foo.jpg" → "foo"). */
export function stem(filename: string): string {
  const base = filename.split('/').pop() ?? filename
  const dot = base.lastIndexOf('.')
  return dot > 0 ? base.slice(0, dot) : base
}
