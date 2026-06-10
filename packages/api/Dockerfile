# ── build stage ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS build
WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir hatchling && \
    pip install --no-cache-dir "."

# ── development target ───────────────────────────────────────────────────
FROM build AS development
ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# ── production stage ─────────────────────────────────────────────────────
FROM python:3.12-slim AS production
WORKDIR /app
COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /usr/local/bin /usr/local/bin
COPY alembic/ alembic/
COPY alembic.ini .

# entrypoint: migrate then start
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
