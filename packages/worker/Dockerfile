FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir hatchling && pip install --no-cache-dir -e .
COPY src/ src/
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["celery", "-A", "cvops_worker.celery_app", "worker", "--loglevel=info"]
