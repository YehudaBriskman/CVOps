"""Router tests for the dataset → CVAT review entry point.

Exercises `POST /datasets/{id}/review`: it resolves the dataset's latest commit
into a review set (samples + their annotation revisions), find-or-creates the
project's `human_review` workflow, and dispatches a run. Dispatch goes through
`advance_workflow`, which freezes the resolved inputs onto a child `step.human_
review` run and XADDs a thin doorbell onto the step's `cvat` queue — asserted
against the `fake_redis` client. The step itself never executes (no worker
in-test), which is the correct unit boundary.

Pattern mirrors test_data_sources.py: a minimal FastAPI app mounting only the
datasets router, with `get_session`/`get_current_user` overridden onto the
testcontainers Postgres.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from cvops_api.core.auth import get_current_user
from cvops_api.core.registry import registry
from cvops_api.db.session import get_session
from cvops_api.db.models.annotations import AnnotationRevision
from cvops_api.db.models.auth import Org, User
from cvops_api.db.models.blobs import Blob
from cvops_api.db.models.ontologies import Ontology
from cvops_api.db.models.projects import Project
from cvops_api.db.models.runs import Run
from cvops_api.db.models.samples import DataSource, Sample
from cvops_api.db.models.versioning import Commit, CommitSample, Dataset, Ref
from cvops_api.db.models.workflows import Workflow
from cvops_api.routers import datasets

CVAT_STREAM = "cvat"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def factory(postgres_url: str):
    engine = create_async_engine(postgres_url, echo=False)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


@pytest.fixture
def human_review_step():  # type: ignore[no-untyped-def]
    """Register the real (import-safe) HumanReviewStep so advance_workflow can
    resolve `step.human_review` and route it to the `cvat` queue. cvat_sdk is
    imported lazily inside run(), which never executes here."""
    from cvops_steps.human_review import HumanReviewStep

    step = HumanReviewStep()
    registry.register(step)
    yield step
    registry._store.pop(step.type_key, None)


def _client(factory, current_user: User) -> AsyncClient:
    app = FastAPI()
    app.include_router(datasets.router)

    async def _get_session_dep():
        async with factory() as sess:
            yield sess

    app.dependency_overrides[get_session] = _get_session_dep
    app.dependency_overrides[get_current_user] = lambda: current_user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed(factory, *, with_commit: bool, n_samples: int = 2, with_revisions: bool = True):
    """Seed org + user + project + dataset. When with_commit, also seed an
    ontology, samples, their annotation revisions, a commit, commit_samples, and
    a `main` branch ref pointing at it.

    Returns (user, project, dataset, [(sample_id, revision_id), ...]).
    """
    suffix = uuid.uuid4().hex[:8]
    pairs: list[tuple[uuid.UUID, uuid.UUID]] = []
    async with factory() as s:
        org = Org(name=f"org-{suffix}")
        s.add(org)
        await s.flush()
        user = User(org_id=org.id, email=f"u-{suffix}@test.com")
        s.add(user)
        project = Project(org_id=org.id, name=f"proj-{suffix}")
        s.add(project)
        await s.flush()
        dataset = Dataset(project_id=project.id, name=f"ds-{suffix}")
        s.add(dataset)
        await s.flush()

        if with_commit:
            ont = Ontology(project_id=project.id, name=f"ont-{suffix}", version=1)
            s.add(ont)
            ds = DataSource(project_id=project.id, type="video", status="uploaded")
            s.add(ds)
            await s.flush()
            commit = Commit(
                dataset_id=dataset.id,
                project_id=project.id,
                ontology_id=ont.id,
                ontology_version=1,
                message="seed",
                stats={"sample_count": n_samples},
            )
            s.add(commit)
            await s.flush()
            for i in range(n_samples):
                h = "sha256:" + uuid.uuid4().hex.ljust(64, "0")
                s.add(
                    Blob(
                        hash=h,
                        storage_backend="s3",
                        storage_key=f"blobs/{h}",
                        size_bytes=10,
                        media_type="image/png",
                    )
                )
                await s.flush()
                sample = Sample(
                    project_id=project.id,
                    source_id=ds.id,
                    blob_hash=h,
                    width=640,
                    height=480,
                    frame_index=i,
                )
                s.add(sample)
                await s.flush()
                rev_id = None
                if with_revisions:
                    rev = AnnotationRevision(
                        project_id=project.id,
                        sample_id=sample.id,
                        ontology_id=ont.id,
                        ontology_version=1,
                        revision_no=1,
                        payload=[],
                        provenance={"source": "model"},
                    )
                    s.add(rev)
                    await s.flush()
                    rev_id = rev.id
                s.add(
                    CommitSample(
                        commit_id=commit.id,
                        sample_id=sample.id,
                        annotation_revision_id=rev_id,
                        split="train",
                    )
                )
                pairs.append((sample.id, rev_id))
            s.add(
                Ref(
                    dataset_id=dataset.id,
                    ref_type="branch",
                    name="main",
                    target_commit_id=commit.id,
                    is_mutable=True,
                )
            )

        await s.commit()
        await s.refresh(user)
        await s.refresh(project)
        await s.refresh(dataset)
        return user, project, dataset, pairs


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_review_dispatches_human_review_run(
    factory, fake_redis, human_review_step
) -> None:
    user, project, dataset, pairs = await _seed(factory, with_commit=True)
    sample_ids = {str(sid) for sid, _ in pairs}
    revision_ids = {str(rid) for _, rid in pairs}

    async with _client(factory, user) as c:
        res = await c.post(f"/datasets/{dataset.id}/review")

    assert res.status_code == 200
    run_id = res.json()["run_id"]
    assert run_id is not None

    async with factory() as s:
        parent = await s.get(Run, uuid.UUID(run_id))
        assert parent is not None
        assert parent.kind == "workflow"
        assert parent.status == "pending"
        assert set(parent.input_refs["params"]["sample_ids"]) == sample_ids
        assert set(parent.input_refs["params"]["annotation_revision_ids"]) == revision_ids

        # A find-or-created human_review workflow now exists for the project.
        wf = (
            (
                await s.execute(
                    select(Workflow).where(
                        Workflow.project_id == project.id,
                        Workflow.name == "human_review",
                    )
                )
            )
            .scalars()
            .one()
        )
        assert parent.workflow_id == wf.id

        # advance_workflow froze the resolved review set onto one child step run.
        children = (
            (await s.execute(select(Run).where(Run.parent_run_id == parent.id)))
            .scalars()
            .all()
        )
        assert len(children) == 1
        child = children[0]
        assert child.kind == "step"
        assert child.step_type == "step.human_review"
        assert child.status == "pending"
        assert set(child.input_refs["sample_ids"]) == sample_ids
        assert set(child.input_refs["annotation_revision_ids"]) == revision_ids

    # One thin doorbell on the cvat queue, pointing at the child step run.
    assert await fake_redis.xlen(CVAT_STREAM) == 1
    _msg_id, fields = (await fake_redis.xrange(CVAT_STREAM))[0]
    assert fields == {
        "job_id": str(child.id),
        "step_type": "step.human_review",
        "queue": CVAT_STREAM,
    }


async def test_review_omits_null_revision_ids(
    factory, fake_redis, human_review_step
) -> None:
    """Samples committed without a pre-label (annotation_revision_id NULL) must
    not stringify to "None" in the dispatched params — that later fails the
    uuid[] cast in human_review (regression: asyncpg DataError 'invalid UUID')."""
    user, project, dataset, pairs = await _seed(
        factory, with_commit=True, with_revisions=False
    )
    sample_ids = {str(sid) for sid, _ in pairs}

    async with _client(factory, user) as c:
        res = await c.post(f"/datasets/{dataset.id}/review")

    assert res.status_code == 200
    async with factory() as s:
        parent = await s.get(Run, uuid.UUID(res.json()["run_id"]))
        assert set(parent.input_refs["params"]["sample_ids"]) == sample_ids
        # All samples were unlabelled → no revision ids, and crucially no "None".
        revs = parent.input_refs["params"]["annotation_revision_ids"]
        assert revs == []
        assert "None" not in revs


async def test_review_reuses_existing_workflow(
    factory, fake_redis, human_review_step
) -> None:
    user, project, dataset, _pairs = await _seed(factory, with_commit=True)

    async with _client(factory, user) as c:
        first = await c.post(f"/datasets/{dataset.id}/review")
        second = await c.post(f"/datasets/{dataset.id}/review")

    assert first.status_code == second.status_code == 200

    # Two runs, but only one human_review workflow was provisioned.
    async with factory() as s:
        wfs = (
            (
                await s.execute(
                    select(Workflow).where(
                        Workflow.project_id == project.id,
                        Workflow.name == "human_review",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(wfs) == 1


async def test_review_without_commit_returns_400(factory) -> None:
    user, _project, dataset, _pairs = await _seed(factory, with_commit=False)

    async with _client(factory, user) as c:
        res = await c.post(f"/datasets/{dataset.id}/review")

    assert res.status_code == 400


async def test_review_missing_dataset_returns_404(factory) -> None:
    user, _project, _dataset, _pairs = await _seed(factory, with_commit=False)

    async with _client(factory, user) as c:
        res = await c.post(f"/datasets/{uuid.uuid4()}/review")

    assert res.status_code == 404


async def test_review_cross_org_returns_404(factory) -> None:
    _owner, _project, dataset, _pairs = await _seed(factory, with_commit=True)
    other, _p2, _ds2, _pairs2 = await _seed(factory, with_commit=False)

    async with _client(factory, other) as c:
        res = await c.post(f"/datasets/{dataset.id}/review")

    assert res.status_code == 404
