"""Unit tests for export_yolo's pure helpers (no DB / no storage).

The ``run()`` method needs Postgres + Garage and is covered by the API
integration suite. Here we pin the deterministic, format-critical staticmethods:
YOLO label formatting, data.yaml rendering, and byte-reproducible tar.gz.
"""

from __future__ import annotations

import gzip
import io
import tarfile

from cvops_steps.export_yolo import ExportYoloStep


# ── _label_lines ─────────────────────────────────────────────────────────────


def test_label_lines_formats_class_id_and_normalized_coords():
    class_index = {"person": 0, "car": 1}
    payload = [
        {"class_key": "person", "geometry": {"type": "bbox", "coords": [0.5, 0.5, 0.2, 0.3]}},
        {"class_key": "car", "geometry": {"type": "bbox", "coords": [0.1, 0.2, 0.3, 0.4]}},
    ]
    out = ExportYoloStep._label_lines(payload, class_index)
    assert out == (
        "0 0.500000 0.500000 0.200000 0.300000\n"
        "1 0.100000 0.200000 0.300000 0.400000\n"
    )


def test_label_lines_skips_classes_not_in_ontology():
    class_index = {"person": 0}
    payload = [
        {"class_key": "person", "geometry": {"coords": [0.5, 0.5, 0.2, 0.2]}},
        {"class_key": "alien", "geometry": {"coords": [0.1, 0.1, 0.1, 0.1]}},
    ]
    out = ExportYoloStep._label_lines(payload, class_index)
    # Only the known class survives; the unknown one is dropped, not guessed.
    assert out == "0 0.500000 0.500000 0.200000 0.200000\n"


def test_label_lines_skips_malformed_coords():
    class_index = {"person": 0}
    payload = [
        {"class_key": "person", "geometry": {"coords": [0.5, 0.5, 0.2]}},  # too few
        {"class_key": "person", "geometry": {"coords": None}},
        {"class_key": "person", "geometry": {}},  # no coords
        {"class_key": "person"},  # no geometry
        {"class_key": "person", "geometry": {"coords": [0.1, 0.2, 0.3, 0.4]}},  # valid
    ]
    out = ExportYoloStep._label_lines(payload, class_index)
    assert out == "0 0.100000 0.200000 0.300000 0.400000\n"


def test_label_lines_empty_payload_is_empty_string():
    # No trailing newline when there are no boxes (empty label file).
    assert ExportYoloStep._label_lines([], {"person": 0}) == ""


# ── _data_yaml ───────────────────────────────────────────────────────────────


def test_data_yaml_lists_classes_in_order():
    yaml = ExportYoloStep._data_yaml(["person", "car", "dog"])
    assert "nc: 3\n" in yaml
    assert 'names: ["person", "car", "dog"]\n' in yaml
    assert "train: images/train\n" in yaml
    assert "val: images/val\n" in yaml
    assert "test: images/test\n" in yaml


def test_data_yaml_quotes_class_names_with_special_chars():
    yaml = ExportYoloStep._data_yaml(['traffic light'])
    assert 'names: ["traffic light"]' in yaml


# ── _make_tar_gz determinism ─────────────────────────────────────────────────


def test_make_tar_gz_is_byte_reproducible():
    entries = [
        ("data.yaml", b"nc: 1\n"),
        ("images/train/a.jpg", b"\xff\xd8imgA"),
        ("labels/train/a.txt", b"0 0.5 0.5 0.1 0.1\n"),
    ]
    a = ExportYoloStep._make_tar_gz(entries)
    b = ExportYoloStep._make_tar_gz(entries)
    assert a == b


def test_make_tar_gz_independent_of_input_order():
    e1 = [("b.txt", b"B"), ("a.txt", b"A")]
    e2 = [("a.txt", b"A"), ("b.txt", b"B")]
    assert ExportYoloStep._make_tar_gz(e1) == ExportYoloStep._make_tar_gz(e2)


def test_make_tar_gz_members_sorted_with_fixed_metadata():
    entries = [("z.txt", b"Z"), ("a.txt", b"A")]
    raw = gzip.decompress(ExportYoloStep._make_tar_gz(entries))
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r") as tar:
        members = tar.getmembers()
    assert [m.name for m in members] == ["a.txt", "z.txt"]
    for m in members:
        assert m.mtime == 0
        assert m.uid == 0 and m.gid == 0
        assert m.uname == "" and m.gname == ""


def test_make_tar_gz_roundtrips_content():
    entries = [("dir/f.bin", b"hello-bytes")]
    raw = gzip.decompress(ExportYoloStep._make_tar_gz(entries))
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r") as tar:
        extracted = tar.extractfile("dir/f.bin").read()
    assert extracted == b"hello-bytes"
