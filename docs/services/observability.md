# ICD — Observability (logs + infra metrics)

**Owner:** TBD
**Last updated:** 2026-06-16

---

## What it is

An opt-in **logs + infra-metrics** stack, gated behind a single Compose profile:

```bash
cd manifests
docker compose --profile observability up -d
```

It is **not** wired into Tilt (it would add churn to the inner loop) and it does
**not** scrape application `/metrics` — services expose no Prometheus endpoint.
Coverage is container/host/datastore level only. Grafana: **http://localhost:3001**.

> Distinct from CVAT's own `cvat_grafana` (ClickHouse-backed, behind traefik) —
> that one is part of the CVAT analytics stack, not this.

---

## Components

| Service | Image | Role |
|---|---|---|
| `loki` | grafana/loki | Log store (filesystem, 7-day retention) |
| `promtail` | grafana/promtail | Docker SD → ships every container's stdout/stderr to Loki |
| `prometheus` | prom/prometheus | Scrapes the exporters below (7-day retention) |
| `cadvisor` | gcr.io/cadvisor/cadvisor | Per-container CPU / mem / net / fs |
| `node-exporter` | prom/node-exporter | Host CPU / mem / disk / network |
| `postgres-exporter` | prometheuscommunity/postgres-exporter | Postgres connections, xacts, tuples |
| `redis-exporter` | oliver006/redis_exporter | Redis clients, commands, memory, keyspace |
| `grafana` | grafana/grafana-oss | Dashboards + Explore (host port 3001) |

Named volumes: `loki_data`, `prometheus_data`, `grafana_data`.

---

## Logs

Promtail discovers containers via the Docker daemon socket and relabels Compose
metadata, so in Grafana logs are filterable by `compose_service`,
`compose_project`, and `container`. The **CVOps · Logs (Loki)** dashboard has a
`compose_service` template variable — pick `worker-training` to watch a training
run stream in, or `api` / `worker-cvat`, etc.

---

## Metrics

Prometheus scrapes only the infra exporters (`prometheus.yml`). Provisioned
Grafana dashboards: **cAdvisor** (containers), **node-exporter** (host),
**PostgreSQL**, **Redis**. All datasources and dashboards are provisioned from
`manifests/observability/grafana/provisioning/` — no manual setup.

---

## Config & env

```
manifests/observability/
  loki-config.yml          promtail-config.yml      prometheus.yml
  grafana/provisioning/{datasources,dashboards}/*.yml
  grafana/dashboards/{logs,cadvisor,node,postgres,redis}.json
```

Env (in `manifests/.env` / `.env.example`):

```
GRAFANA_ADMIN_PASSWORD   Grafana admin login (user: admin)
POSTGRES_EXPORTER_DSN    postgresql://cvops:<pw>@postgres:5432/cvops?sslmode=disable
REDIS_EXPORTER_ADDR      redis://redis:6379
```

---

## Verify

```bash
docker compose --profile observability up -d
# Grafana :3001 → Loki logs filterable by compose service (worker-training stream);
# Prometheus dashboards (cAdvisor / postgres / redis) populated;
# Status → Targets: all scrape targets `up`.
```
