# ICD — MLflow Tracking Server

**Owner:** Ben
**Last updated:** 2026-06-15

---

## What it is

A standalone [MLflow](https://mlflow.org/) tracking server wired into the CVOps
stack. Trainers dispatched by `step.train` log parameters, metrics, and
artifacts to it; the model page then resolves the **MLflow run** link to the
actual run in the UI.

It comes up automatically with the infra — it's a **no-profile** compose service
(like `nginx`/`garage-init`), so both `tilt up` and `docker compose --profile
app/all up` start it. UI: **http://localhost:5000**.

```
trainer subprocess ──log──► mlflow :5000 ──backend──► Postgres (mlflow DB)
   (MLFLOW_TRACKING_URI)        │
                               └──artifacts (proxied)──► Garage s3://<bucket>/mlflow
browser ──"MLflow run" link──► mlflow :5000  (VITE_MLFLOW_URL)
```

---

## Design

**Backend store — separate Postgres `mlflow` database.** MLflow auto-manages its
own schema; it must never share the Alembic-managed `cvops` database. The
one-shot `mlflow-init` service creates the `mlflow` database idempotently
(mirrors `garage-init`). MLflow uses the **sync `psycopg2`** driver:
`postgresql://cvops:…@postgres:5432/mlflow`.

**Artifact store — Garage S3, proxied.** The server runs with
`--serve-artifacts --artifacts-destination s3://<bucket>/mlflow`. It holds the S3
credentials; the trainer and the browser reach artifacts **through** the server,
so:

- the worker only needs `MLFLOW_TRACKING_URI`, and
- the browser only needs the `:5000` origin.

Neither needs Garage credentials.

**Image.** The upstream `ghcr.io/mlflow/mlflow` image ships neither the Postgres
driver nor the S3 client, so `services/mlflow/Dockerfile` adds `psycopg2-binary`
and `boto3` on top.

---

## Environment

| Service | Variable | Value | Why |
|---|---|---|---|
| `mlflow` | `MLFLOW_S3_ENDPOINT_URL` | `http://garage:3900` | artifact target |
| `mlflow` | `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Garage default key | artifact auth |
| `worker-training` | `MLFLOW_TRACKING_URI` | `http://mlflow:5000` | forwarded into the trainer by `train.py` |
| `frontend` (build arg) | `VITE_MLFLOW_URL` | `http://localhost:5000` | baked into the bundle; the model-page link origin |

`VITE_MLFLOW_URL` is a **build-time** Vite var — unlike the S3 presign host
(derived per-request from the `Host` header), it cannot be set per-request. VM
devs must point it at their VM host, e.g. `http://my-dev-vm:5000`.

No step code changed for this: `train.py` `_build_env` already forwards
`MLFLOW_TRACKING_URI`, and `_write_model_version` already extracts
`mlflow_run_id` from the trainer's `metrics.json`.

---

## Trainer convention

The cloned trainer repo must:

1. Call `mlflow.start_run()` (autolog or manual) — `MLFLOW_TRACKING_URI` is
   already in its environment, so no URI wiring is needed inside the container.
2. Write its run id as `mlflow_run_id` into `OUTPUT_DIR/metrics.json`:

   ```json
   { "mAP50": 0.87, "loss": 0.043, "mlflow_run_id": "abc123def456" }
   ```

   `_write_model_version` reads this into `model_versions.mlflow_run_id`.

3. Log to the **Default experiment** (id `0`) for now — see the caveat below.

---

## Caveat: experiment id is hard-coded to 0

`ModelDetail.tsx` builds the link as
`${VITE_MLFLOW_URL}/#/experiments/0/runs/${mlflow_run_id}` — experiment `0` is
MLflow's "Default". So the trainer convention is "log to the Default
experiment" and the link is exact.

Per-project experiments would need an `mlflow_experiment_id` column on
`ModelVersion` plus a link tweak. **Out of scope** — noted as a follow-up.

---

## Verification

```bash
cd manifests && docker compose --profile all up --build
# → mlflow-init creates the `mlflow` DB once and exits 0
# → mlflow becomes healthy; http://localhost:5000 serves the UI
```

Restart the stack and re-trigger to confirm `mlflow-init` is idempotent (DB
already exists → no error) and prior runs persist (Postgres-backed).

End-to-end: trigger **Train this commit** against a trainer that calls
`mlflow.start_run()` and emits `mlflow_run_id`; after it succeeds, open the model
on the Models page and confirm the **MLflow run** link opens that run, with
artifacts visible (proxied through Garage).
