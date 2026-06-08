import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from cvops_api.db.models.projects import Project
from tests.db.conftest import make_org, make_project


async def test_project_create(session: AsyncSession):
    org = await make_org(session)
    project = Project(org_id=org.id, name="my-project")
    session.add(project)
    await session.flush()

    assert project.id is not None
    assert project.name == "my-project"
    assert project.org_id == org.id


async def test_project_task_type_default(session: AsyncSession):
    org = await make_org(session)
    project = Project(org_id=org.id, name="default-task-project")
    session.add(project)
    await session.flush()
    await session.refresh(project)

    assert project.task_type == "detection"


async def test_project_org_id_fk(session: AsyncSession):
    fake_org_id = uuid.uuid4()
    project = Project(org_id=fake_org_id, name="orphan-project")
    session.add(project)

    with pytest.raises(IntegrityError):
        await session.flush()

    await session.rollback()


async def test_project_settings_nullable(session: AsyncSession):
    org = await make_org(session)
    project = Project(org_id=org.id, name="no-settings-project")
    session.add(project)
    await session.flush()

    assert project.settings is None


async def test_project_settings_jsonb(session: AsyncSession):
    org = await make_org(session)
    project = Project(org_id=org.id, name="settings-project", settings={"retention_days": 30})
    session.add(project)
    await session.flush()
    await session.refresh(project)

    assert project.settings["retention_days"] == 30


async def test_project_default_ontology_nullable(session: AsyncSession):
    org = await make_org(session)
    project = Project(org_id=org.id, name="no-ontology-project")
    session.add(project)
    await session.flush()

    assert project.default_ontology_id is None


async def test_project_soft_delete(session: AsyncSession):
    project = await make_project(session)

    project.deleted_at = datetime.now(UTC)
    await session.flush()
    await session.refresh(project)

    assert project.deleted_at is not None
    result = await session.get(Project, project.id)
    assert result is not None


async def test_multiple_projects_same_org(session: AsyncSession):
    org = await make_org(session)
    project_a = Project(org_id=org.id, name="project-alpha")
    project_b = Project(org_id=org.id, name="project-beta")
    session.add(project_a)
    session.add(project_b)
    await session.flush()

    assert project_a.id != project_b.id
    assert project_a.org_id == project_b.org_id
