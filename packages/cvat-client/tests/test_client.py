"""Unit tests for the cvat-client wrapper (``cvops_cvat_client.client``).

The module lazily imports ``cvat_sdk`` inside each function and routes every
real call through ``_client()`` (which logs into a live CVAT server). No server
is available in tests, so we monkeypatch ``_client`` to a fake and replace the
handful of ``cvat_sdk`` request/model classes the functions construct. That
leaves the wrapper's OWN logic under test: URL building, payload assembly,
response transformation, the auto-annotate polling loop, and geometry
round-tripping (via the real, pure ``geometry`` helpers).

These tests deliberately do NOT assert exact SDK call shapes against a real
CVAT (the module docstring flags those as provisional); they pin the
transformation logic the workers depend on.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from cvops_cvat_client import client as cc


# --------------------------------------------------------------------------- #
# _task_url — pure
# --------------------------------------------------------------------------- #


def test_task_url_with_job() -> None:
    url = cc._task_url(7, 42)
    assert url == f"{cc.CVAT_PUBLIC_URL}/tasks/7/jobs/42"


def test_task_url_without_job() -> None:
    url = cc._task_url(7)
    assert url == f"{cc.CVAT_PUBLIC_URL}/tasks/7/jobs"


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #


class _FakeLambdaApi:
    """Stand-in for cvat_sdk LambdaApi. Behaviour is driven by class attrs set
    per-test so the wrapper's transformation code runs unchanged."""

    functions_json = "[]"
    create_result = SimpleNamespace(id="req-1")
    statuses: list[str] = ["finished"]

    def __init__(self, _api_client) -> None:
        self._status_iter = iter(self.statuses)

    def list_functions(self):
        return None, SimpleNamespace(data=self.functions_json)

    def create_requests(self, _req):
        return self.create_result, None

    def retrieve_requests(self, id):  # noqa: A002 - mirrors sdk kwarg
        return SimpleNamespace(status=next(self._status_iter)), None


def _jobs_api_returning(job_ids: list[int]):
    results = [SimpleNamespace(id=j) for j in job_ids]
    page = SimpleNamespace(results=results)

    class _JobsApi:
        def list(self, task_id):  # noqa: ARG002
            return [page]

    return _JobsApi()


def _fake_client(jobs_ids: list[int] | None = None):
    """A fake cvat_sdk Client with just the attributes the wrapper touches."""
    return SimpleNamespace(
        api_client=SimpleNamespace(jobs_api=_jobs_api_returning(jobs_ids or [99])),
        tasks=SimpleNamespace(),
    )


# --------------------------------------------------------------------------- #
# list_models — field mapping
# --------------------------------------------------------------------------- #


def test_list_models_maps_fields(monkeypatch) -> None:
    _FakeLambdaApi.functions_json = json.dumps(
        [
            {"id": "yolo", "name": "YOLOv8", "kind": "detector", "description": "d"},
            {"id": "bare"},  # exercises the .get defaults
        ]
    )
    monkeypatch.setattr(cc, "_client", lambda: _fake_client())
    monkeypatch.setattr("cvat_sdk.api_client.apis.LambdaApi", _FakeLambdaApi)

    out = cc.list_models()

    assert out == [
        {"id": "yolo", "name": "YOLOv8", "kind": "detector", "description": "d"},
        {"id": "bare", "name": "bare", "kind": "", "description": ""},
    ]


# --------------------------------------------------------------------------- #
# annotate — task create + Nuclio poll loop
# --------------------------------------------------------------------------- #


@pytest.fixture
def _patch_annotate_sdk(monkeypatch):
    """Patch the sdk symbols annotate() imports, plus time.sleep."""
    monkeypatch.setattr("cvat_sdk.models.TaskWriteRequest", lambda **kw: SimpleNamespace(**kw))
    monkeypatch.setattr(
        "cvat_sdk.api_client.models.FunctionCallRequest",
        lambda **kw: SimpleNamespace(**kw),
    )
    monkeypatch.setattr(cc.time, "sleep", lambda *_: None)


def _client_with_created_task(monkeypatch, jobs_ids=(99,)):
    created = SimpleNamespace(id=5, upload_data=lambda **kw: None, set_annotations=lambda *a: None)
    fake = _fake_client(list(jobs_ids))
    fake.tasks.create = lambda *_a, **_k: created
    fake.tasks.retrieve = lambda _id: created
    monkeypatch.setattr(cc, "_client", lambda: fake)
    return created


def test_annotate_returns_task_job_url(monkeypatch, _patch_annotate_sdk) -> None:
    _FakeLambdaApi.statuses = ["running", "finished"]
    monkeypatch.setattr("cvat_sdk.api_client.apis.LambdaApi", _FakeLambdaApi)
    _client_with_created_task(monkeypatch, jobs_ids=(77,))

    out = cc.annotate("t", "fn", [], threshold=0.5)

    assert out == {"task_id": 5, "job_id": 77, "cvat_url": cc._task_url(5, 77)}


def test_annotate_raises_on_failed_status(monkeypatch, _patch_annotate_sdk) -> None:
    _FakeLambdaApi.statuses = ["failed"]
    monkeypatch.setattr("cvat_sdk.api_client.apis.LambdaApi", _FakeLambdaApi)
    _client_with_created_task(monkeypatch)

    with pytest.raises(RuntimeError, match="Auto-annotation failed"):
        cc.annotate("t", "fn", [])


# --------------------------------------------------------------------------- #
# pull_review_task — annotation download + normalization + grouping
# --------------------------------------------------------------------------- #


def test_pull_review_task_groups_and_normalizes(monkeypatch) -> None:
    labels = [SimpleNamespace(id=10, name="car"), SimpleNamespace(id=11, name="person")]
    shapes = [
        # frame 0: a valid rectangle (car)
        SimpleNamespace(type="rectangle", frame=0, label_id=10, points=[0.0, 0.0, 100.0, 100.0]),
        # frame 0: a second rectangle (person)
        SimpleNamespace(type="rectangle", frame=0, label_id=11, points=[10.0, 10.0, 50.0, 50.0]),
        # frame 1: a polygon → skipped (detection-only)
        SimpleNamespace(type="polygon", frame=1, label_id=10, points=[0, 0, 1, 1, 2, 2]),
        # frame 9: out of range → skipped
        SimpleNamespace(type="rectangle", frame=9, label_id=10, points=[0, 0, 10, 10]),
    ]
    task = SimpleNamespace(
        get_labels=lambda: labels,
        get_annotations=lambda: SimpleNamespace(shapes=shapes),
    )
    fake = _fake_client()
    fake.tasks.retrieve = lambda _id: task
    monkeypatch.setattr(cc, "_client", lambda: fake)

    out = cc.pull_review_task(123, frame_dims=[(200, 200), (200, 200)])

    assert set(out.keys()) == {0}  # frame 1 polygon + frame 9 OOR both omitted
    assert len(out[0]) == 2
    keys = {a["class_key"] for a in out[0]}
    assert keys == {"car", "person"}
    for ann in out[0]:
        assert ann["geometry"]["type"] == "bbox"
        coords = ann["geometry"]["coords"]
        assert len(coords) == 4
        assert all(0.0 <= c <= 1.0 for c in coords)


def test_pull_review_task_empty_when_no_rectangles(monkeypatch) -> None:
    task = SimpleNamespace(
        get_labels=lambda: [],
        get_annotations=lambda: SimpleNamespace(shapes=[]),
    )
    fake = _fake_client()
    fake.tasks.retrieve = lambda _id: task
    monkeypatch.setattr(cc, "_client", lambda: fake)

    assert cc.pull_review_task(1, frame_dims=[(100, 100)]) == {}


# --------------------------------------------------------------------------- #
# push_review_task — label set + shape building + skip rules
# --------------------------------------------------------------------------- #


@pytest.fixture
def _patch_push_sdk(monkeypatch):
    monkeypatch.setattr("cvat_sdk.models.TaskWriteRequest", lambda **kw: SimpleNamespace(**kw))
    monkeypatch.setattr("cvat_sdk.models.LabeledShapeRequest", lambda **kw: SimpleNamespace(**kw))
    monkeypatch.setattr("cvat_sdk.models.LabeledDataRequest", lambda **kw: SimpleNamespace(**kw))


def test_push_review_task_builds_shapes_and_skips_invalid(monkeypatch, _patch_push_sdk) -> None:
    set_annotations_calls: list = []
    created = SimpleNamespace(
        id=8,
        upload_data=lambda **kw: None,
        get_labels=lambda: [
            SimpleNamespace(id=10, name="car"),
            SimpleNamespace(id=11, name="dog"),
        ],
        set_annotations=lambda data: set_annotations_calls.append(data),
    )
    captured_labels = {}
    fake = _fake_client([55])

    def _create(req):
        captured_labels["labels"] = req.labels
        return created

    fake.tasks.create = _create
    monkeypatch.setattr(cc, "_client", lambda: fake)

    images = [
        cc.ReviewImage(
            path="/tmp/a.jpg",
            width=200,
            height=200,
            annotations=[
                {
                    "class_key": "car",
                    "geometry": {"coords": [0.5, 0.5, 0.2, 0.2]},
                },  # valid
                {
                    "class_key": "dog",
                    "geometry": {"coords": [0.1, 0.1]},
                },  # bad coords → skip
                {
                    "class_key": "ghost",
                    "geometry": {"coords": [0.5, 0.5, 0.2, 0.2]},
                },  # no label → skip
            ],
        )
    ]

    out = cc.push_review_task("review", images)

    # label set is the distinct, non-empty class_keys across all annotations, sorted
    assert sorted(lbl["name"] for lbl in captured_labels["labels"]) == [
        "car",
        "dog",
        "ghost",
    ]
    # only the one valid annotation became a shape
    assert len(set_annotations_calls) == 1
    assert len(set_annotations_calls[0].shapes) == 1
    shape = set_annotations_calls[0].shapes[0]
    assert shape.label_id == 10
    assert shape.frame == 0
    assert shape.type == "rectangle"
    assert out["task_id"] == 8
    assert out["job_ids"] == [55]
    assert out["cvat_url"] == cc._task_url(8, 55)
    assert out["label_map"] == {"car": 10, "dog": 11}


def test_push_review_task_no_shapes_skips_set_annotations(monkeypatch, _patch_push_sdk) -> None:
    set_annotations_calls: list = []
    created = SimpleNamespace(
        id=8,
        upload_data=lambda **kw: None,
        get_labels=lambda: [],
        set_annotations=lambda data: set_annotations_calls.append(data),
    )
    fake = _fake_client([1])
    fake.tasks.create = lambda req: created
    monkeypatch.setattr(cc, "_client", lambda: fake)

    images = [cc.ReviewImage(path="/tmp/a.jpg", width=200, height=200, annotations=[])]
    out = cc.push_review_task("review", images)

    assert set_annotations_calls == []  # no shapes → set_annotations never called
    assert out["label_map"] == {}


# --------------------------------------------------------------------------- #
# register_webhook
# --------------------------------------------------------------------------- #


def test_register_webhook_returns_id(monkeypatch) -> None:
    # raising=False: these symbol names are how the wrapper imports them, but
    # they have drifted across cvat_sdk versions (e.g. 2.68 renamed
    # WebhookContentTypeEnum → WebhookContentType), so inject them to exercise
    # the wrapper's own request-assembly logic regardless of the pinned sdk.
    monkeypatch.setattr("cvat_sdk.api_client.models.EventsEnum", lambda v: v, raising=False)
    monkeypatch.setattr(
        "cvat_sdk.api_client.models.WebhookContentTypeEnum", lambda v: v, raising=False
    )
    monkeypatch.setattr(
        "cvat_sdk.api_client.models.WebhookWriteRequest",
        lambda **kw: SimpleNamespace(**kw),
        raising=False,
    )

    captured: dict = {}

    class _WebhooksApi:
        def create(self, req):
            captured["req"] = req
            return SimpleNamespace(id=321), None

    fake = _fake_client()
    fake.api_client.webhooks_api = _WebhooksApi()
    monkeypatch.setattr(cc, "_client", lambda: fake)

    wid = cc.register_webhook(task_id=5, target_url="http://hook", secret="s3cr3t")

    assert wid == 321
    assert captured["req"].target_url == "http://hook"
    assert captured["req"].secret == "s3cr3t"
    assert captured["req"].task_id == 5
