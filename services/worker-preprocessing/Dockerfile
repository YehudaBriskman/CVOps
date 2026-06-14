FROM python:3.12-slim

WORKDIR /app

# Shared packages first — layer cache survives worker code changes
COPY services/api        ./services/api
COPY packages/worker-common ./packages/worker-common
COPY packages/steps      ./packages/steps
RUN pip install --no-cache-dir \
    ./services/api \
    ./packages/worker-common \
    ./packages/steps
;
COPY services/worker-preprocessing ./services/worker-preprocessing
RUN pip install --no-cache-dir ./services/worker-preprocessing

ENV PYTHONUNBUFFERED=1

RUN groupadd --system --gid 1001 app && \
    useradd --system --uid 1001 --gid app --home /app --shell /usr/sbin/nologin app
USER 1001:1001

CMD ["python", "-m", "worker_preprocessing.main"]
