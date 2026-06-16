"""Regression for pull_review_task shape parsing.

CVAT's reviewed shapes carry a ``type`` that is a cvat_sdk enum — its ``str()``
is ``"rectangle"`` but it is NOT equal to the bare string. The pull filtered
with ``shape.type != "rectangle"``, which was always true for the enum, so every
reviewed box was dropped and nothing imported. The client mock below reproduces
that enum behavior; the test pins that rectangles are now kept.
"""

from cvops_cvat_client import client as cvat_client


class _RectType:
    """Stringifies to 'rectangle' but is not == the bare string (like the SDK enum)."""

    def __str__(self) -> str:
        return "rectangle"


class _Shape:
    type = _RectType()
    frame = 0
    label_id = 1
    points = [64.0, 48.0, 128.0, 96.0]


class _Label:
    id = 1
    name = "plane"


class _Data:
    shapes = [_Shape()]


class _Task:
    def get_labels(self):
        return [_Label()]

    def get_annotations(self):
        return _Data()


class _FakeClient:
    class tasks:
        @staticmethod
        def retrieve(task_id):
            return _Task()


def test_pull_keeps_enum_typed_rectangles(monkeypatch):
    monkeypatch.setattr(cvat_client, "_client", lambda: _FakeClient())

    out = cvat_client.pull_review_task(1, [(640, 480)])

    assert list(out.keys()) == [0]  # the one reviewed frame, not dropped
    ann = out[0][0]
    assert ann["class_key"] == "plane"
    assert ann["geometry"]["type"] == "bbox"
    assert len(ann["geometry"]["coords"]) == 4
