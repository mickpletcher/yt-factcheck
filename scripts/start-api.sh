#!/usr/bin/env sh
set -eu

WEB_CONCURRENCY="${WEB_CONCURRENCY:-2}"
WEB_TIMEOUT="${WEB_TIMEOUT:-120}"
WEB_BIND="${WEB_BIND:-0.0.0.0:8000}"

exec gunicorn evidencechain.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers "$WEB_CONCURRENCY" \
    --bind "$WEB_BIND" \
    --timeout "$WEB_TIMEOUT" \
    --access-logfile - \
    --error-logfile -
