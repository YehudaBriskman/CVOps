import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from cvops_api.db.models.workflows import Workflow
from tests.db.conftest import make_project


async def test_workflow_create(session: AsyncSession):
    project = await make_project(session)
    wf = Workflow(
        project_id=project.id,
        name="my-workflow",
        definition={"steps": [], "edges": []},
    )
    session.add(wf)
    await session.flush()

    assert wf.id is not None
    assert wf.project_id == project.id
    assert wf.name == "my-workflow"
    assert wf.definition == {"steps": [], "edges": []}


async def test_workflow_version_default(session: AsyncSession):
    project = await make_project(session)
    wf = Workflow(
        project_id=project.id,
        name="versioned-workflow",
        definition={"steps": [], "edges": []},
    )
    session.add(wf)
    await session.flush()
    await session.refresh(wf)

    assert wf.version == 1


async def test_workflow_unique_name_per_project(session: AsyncSession):
    project = await make_project(session)
    wf_a = Workflow(
        project_id=project.id,
        name="duplicate-name",
        definition={"steps": [], "edges": []},
    )
    session.add(wf_a)
    await session.flush()

    wf_b = Workflow(
        project_id=project.id,
        name="duplicate-name",
        definition={"steps": [{"id": "s1"}], "edges": []},
    )
    session.add(wf_b)

    with pytest.raises(IntegrityError):
        await session.flush()

    await session.rollback()


async def test_workflow_definition_jsonb(session: AsyncSession):
    project = await make_project(session)
    complex_definition = {
        "steps": [
            {"id": "step-1", "type": "extract_frames", "config": {"fps": 5}, "inputs": {}},
            {"id": "step-2", "type": "label", "config": {}, "inputs": {"frames": "step-1"}},
        ],
        "edges": [["step-1", "step-2"]],
    }
    wf = Workflow(
        project_id=project.id,
        name="complex-workflow",
        definition=complex_definition,
    )
    session.add(wf)
    await session.flush()
    await session.refresh(wf)

    assert isinstance(wf.definition["steps"], list)
    assert len(wf.definition["steps"]) == 2
    assert wf.definition["steps"][0]["type"] == "extract_frames"
    assert wf.definition["edges"] == [["step-1", "step-2"]]


async def test_workflow_different_projects_same_name(session: AsyncSession):
    project_a = await make_project(session)
    project_b = await make_project(session)

    wf_a = Workflow(
        project_id=project_a.id,
        name="shared-name",
        definition={"steps": [], "edges": []},
    )
    session.add(wf_a)
    await session.flush()

    wf_b = Workflow(
        project_id=project_b.id,
        name="shared-name",
        definition={"steps": [], "edges": []},
    )
    session.add(wf_b)
    await session.flush()

    assert wf_a.id != wf_b.id
    assert wf_a.name == wf_b.name
    assert wf_a.project_id != wf_b.project_id
