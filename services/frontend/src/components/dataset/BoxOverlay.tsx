import type { AnnotationBox } from '../../api/annotations'

/** Deterministic color from a class key, so a given label always renders the
 *  same hue. v1 stopgap until real ontology label_classes.color is wired in. */
function classColor(key: string): string {
  let hash = 0
  for (let i = 0; i < key.length; i++) {
    hash = (hash * 31 + key.charCodeAt(i)) | 0
  }
  const hue = Math.abs(hash) % 360
  return `hsl(${hue}, 80%, 50%)`
}

/** Absolutely-positioned box overlay. Sits over an image-relative container
 *  (parent must be `relative`); the overlay fills it and positions each box by
 *  CSS percentage from normalized center-format coords [cx, cy, w, h]. Malformed
 *  boxes (coords.length !== 4) are skipped, mirroring export_yolo. */
export function BoxOverlay({ boxes }: { boxes: AnnotationBox[] }) {
  return (
    <div className="absolute inset-0 pointer-events-none">
      {boxes.map((box, i) => {
        const coords = box.geometry?.coords
        if (!coords || coords.length !== 4) return null
        const [cx, cy, w, h] = coords
        const color = classColor(box.class_key)
        return (
          <div
            key={i}
            className="absolute border-2"
            style={{
              left: `${(cx - w / 2) * 100}%`,
              top: `${(cy - h / 2) * 100}%`,
              width: `${w * 100}%`,
              height: `${h * 100}%`,
              borderColor: color,
            }}
          >
            <span
              className="absolute top-0 left-0 -translate-y-full text-[10px] font-medium px-1 py-0.5 leading-none text-white whitespace-nowrap rounded-t-sm"
              style={{ backgroundColor: color }}
            >
              {box.class_key}
            </span>
          </div>
        )
      })}
    </div>
  )
}
