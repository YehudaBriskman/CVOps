from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cvops_api.config import settings
from cvops_api.db.session import engine
from cvops_api.routers import (
    auth, orgs, projects, data_sources, samples,
    ontologies, datasets, workflows, runs, models,
    training_containers, registry as registry_router, internal,
)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    # Register all step types into the in-memory registry
    from cvops_steps import register_all  # type: ignore[import]
    register_all()
    yield
    await engine.dispose()


app = FastAPI(
    title="CVOps API",
    version="0.1.0",
    description="ML lifecycle dashboard — dataset versioning, workflow orchestration, training dispatch.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────
app.include_router(auth.router,               prefix="/auth",                tags=["auth"])
app.include_router(registry_router.router,    prefix="/registry",            tags=["registry"])
app.include_router(orgs.router,               prefix="/orgs",                tags=["orgs"])
app.include_router(projects.router,           prefix="/projects",            tags=["projects"])
app.include_router(data_sources.router,       prefix="",                     tags=["data-sources"])
app.include_router(samples.router,            prefix="",                     tags=["samples"])
app.include_router(ontologies.router,         prefix="",                     tags=["ontologies"])
app.include_router(datasets.router,           prefix="",                     tags=["datasets"])
app.include_router(workflows.router,          prefix="",                     tags=["workflows"])
app.include_router(runs.router,               prefix="",                     tags=["runs"])
app.include_router(models.router,             prefix="",                     tags=["models"])
app.include_router(training_containers.router,prefix="",                     tags=["training-containers"])
app.include_router(internal.router,           prefix="/internal",            tags=["internal"])
