"""Geometry conversion between CVOps canonical annotations and CVAT rectangles.

CVOps stores bounding boxes in its canonical annotation payload as a normalized,
center-based box::

    {"type": "bbox", "coords": [cx, cy, w, h]}   # all in 0..1, relative to image

This matches what ``cvops_steps.export_yolo`` writes to YOLO label files
(``<class_id> cx cy w h``), so it is the authoritative on-disk shape.

CVAT represents a rectangle as two absolute-pixel corners::

    points = [x1, y1, x2, y2]   # top-left, bottom-right, in pixels

These helpers are pure and dependency-free (no ``cvat_sdk`` import) so they can
be unit-tested without a CVAT server and imported anywhere cheaply. Conversions
are exact inverses, so a push→pull round-trip recovers the original coords up to
floating-point precision.
"""

from __future__ import annotations

Coords = list[float]


def norm_bbox_to_cvat_rect(coords: Coords, img_w: int, img_h: int) -> Coords:
    """Normalized center box ``[cx, cy, w, h]`` → CVAT pixel rect ``[x1, y1, x2, y2]``.

    Args:
        coords: ``[cx, cy, w, h]``, each in 0..1 relative to the image.
        img_w, img_h: image dimensions in pixels (must be > 0).

    Returns:
        ``[x1, y1, x2, y2]`` in absolute pixels (top-left, bottom-right).
    """
    _validate(coords, img_w, img_h)
    cx, cy, w, h = coords
    x1 = (cx - w / 2) * img_w
    y1 = (cy - h / 2) * img_h
    x2 = (cx + w / 2) * img_w
    y2 = (cy + h / 2) * img_h
    return [x1, y1, x2, y2]


def cvat_rect_to_norm_bbox(points: Coords, img_w: int, img_h: int) -> Coords:
    """CVAT pixel rect ``[x1, y1, x2, y2]`` → normalized center box ``[cx, cy, w, h]``.

    The inverse of :func:`norm_bbox_to_cvat_rect`. Corners are normalized so the
    result is order-independent (a box drawn bottom-up still yields positive w/h).

    Args:
        points: ``[x1, y1, x2, y2]`` in absolute pixels.
        img_w, img_h: image dimensions in pixels (must be > 0).

    Returns:
        ``[cx, cy, w, h]`` each in 0..1 relative to the image.
    """
    _validate(points, img_w, img_h)
    x1, y1, x2, y2 = points
    # Normalize corner order so width/height are non-negative regardless of how
    # the annotator dragged the box.
    left, right = sorted((x1, x2))
    top, bottom = sorted((y1, y2))
    cx = (left + right) / (2 * img_w)
    cy = (top + bottom) / (2 * img_h)
    w = (right - left) / img_w
    h = (bottom - top) / img_h
    return [cx, cy, w, h]


def _validate(coords: Coords, img_w: int, img_h: int) -> None:
    if len(coords) != 4:
        raise ValueError(f"expected 4 coordinates, got {len(coords)}: {coords!r}")
    if img_w <= 0 or img_h <= 0:
        raise ValueError(f"image dimensions must be positive, got {img_w}x{img_h}")
