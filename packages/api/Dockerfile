# ── build stage ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS build
WORKDIR /app
COPY pyproject.toml .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout=300 --retries=10 hatchling && \
    python3 -c "import tomllib,subprocess,sys; f=open('pyproject.toml','rb'); deps=tomllib.load(f)['project']['dependencies']; f.close(); subprocess.run([sys.executable,'-m','pip','install','--timeout=300','--retries=10']+deps,check=True)"
COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-deps --no-build-isolation "."

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
