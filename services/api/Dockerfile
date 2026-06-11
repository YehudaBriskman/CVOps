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
