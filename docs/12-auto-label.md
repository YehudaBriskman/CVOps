# auto_label.py

**Step 2 of 3 in the YOLO workflow**

Runs YOLO12 nano on extracted frames and generates YOLO-format label files (`.txt`) for each image.

---

## What it does

1. Lists available session folders inside `./frames`
2. Asks the user to select a session and set a confidence threshold
3. Runs YOLO12n inference on every image in the session
4. Saves one `.txt` label file per image in YOLO format

**Output structure:**
```
labels/
  <session_name>/
    <session_name>_1.txt
    <session_name>_2.txt
    ...
```

Each `.txt` file contains one detection per line:
```
<class_id> <x_center> <y_center> <width> <height>
```
All coordinates are normalized (0.0–1.0). Files are empty when no objects are detected.

---

## Usage

```bash
cd frame_extractor
python auto_label.py
```

The script prompts interactively:

| Prompt | Example |
|--------|---------|
| Session to label | select from numbered list |
| Confidence threshold | `0.25` (default), range `0.0–1.0` |

---

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `DEFAULT_CONFIDENCE` | `0.25` | Minimum detection confidence |
| Model file | `yolo12n.pt` | Must be present in `frame_extractor/` |

---

## Class IDs

The model uses standard **COCO class IDs** (e.g. `2 = car`, `0 = person`, `7 = truck`). These IDs are written as-is into the `.txt` files and are correctly mapped to class names in the next step (`upload_to_cvat.py`).

---

## Known Limitation — Model Location

> **Note:** The current implementation loads `yolo12n.pt` as a local file and runs inference inside this script. The intended architecture is to have the YOLO12n model deployed **directly on the CVAT server** as an auto-annotation plugin, so that labeling happens inside CVAT itself without a separate script.
>
> Running the model as a standalone script is a temporary workaround. This will be replaced in a future update by integrating YOLO12n as a native CVAT model.

---

## Notes

- Requires `ultralytics` to be installed (`pip install ultralytics`)
- Must be run after `extract_frames.py`
- Higher confidence = fewer but more reliable detections
- Lower confidence = more detections but potentially noisier results