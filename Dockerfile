# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim
RUN groupadd -g 10001 forecaster \
 && useradd -u 10001 -g forecaster -M -s /usr/sbin/nologin forecaster
COPY --from=builder /install /usr/local
USER 10001:10001
WORKDIR /app

# No ENTRYPOINT/CMD: this single image serves two roles in the Helm chart
# (deploy/helm/forecaster) — the read-only API (uvicorn forecaster.api:app)
# and the forecaster-daily/forecaster-calibrate CronJobs (forecaster <cmd>)
# — each workload sets its own command/args.
