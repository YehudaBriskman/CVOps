# ── build stage ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS build
WORKDIR /app
COPY pyproject.toml .
# hatchling's editable install scans for packages at install time, so src/
# must be present before `pip install -e` runs — otherwise the wheel's
# .pth/finder for cvops_api never gets created and `import cvops_api` 404s.
COPY src/ src/
RUN pip install --no-cache-dir hatchling && \
    pip install --no-cache-dir -e ".[dev]"

# Install the step implementations so the in-container registry is populated:
# advance_workflow validates/resolves step types and would reject the ingest
# workflow otherwise. cvops-steps comes from the `steps` named build context
# (see additional_contexts in docker-compose.yml) and is installed non-editable
# so it lands in site-packages and is carried into the production stage. No
# ffmpeg binary needed here — the API never executes steps (the worker does);
# step modules lazy-import their heavy deps inside run().
COPY --from=steps pyproject.toml /tmp/steps/pyproject.toml
COPY --from=steps src /tmp/steps/src
RUN pip install --no-cache-dir /tmp/steps

# ── development target ───────────────────────────────────────────────────
FROM build AS development
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
RUN groupadd --system --gid 1001 app && \
    useradd  --system --uid 1001 --gid app --home /app --shell /usr/sbin/nologin app && \
    chown -R 1001:1001 /app
USER 1001:1001

# ── production stage ─────────────────────────────────────────────────────
FROM python:3.12-slim AS production
WORKDIR /app
COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /usr/local/bin /usr/local/bin
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .

# entrypoint: migrate then start
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh
ENV PYTHONUNBUFFERED=1
EXPOSE 8000

RUN groupadd --system --gid 1001 app && \
    useradd  --system --uid 1001 --gid app --home /app --shell /usr/sbin/nologin app && \
    chown -R 1001:1001 /app
USER 1001:1001

ENTRYPOINT ["./entrypoint.sh"]
