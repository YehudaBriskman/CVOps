# MLflow tracking server for CVOps.
#
# The upstream image ships neither the Postgres driver nor the S3 client, so we
# add them on top:
#   • psycopg2-binary → sync driver for the `mlflow` Postgres backend store.
#   • boto3           → S3 client for proxied artifact serving against Garage.
#
# Everything else (the `mlflow server` entrypoint, the UI) comes from upstream.
# The server command and its env live in manifests/docker-compose.yml.
FROM ghcr.io/mlflow/mlflow:v2.19.0

RUN pip install --no-cache-dir psycopg2-binary boto3
