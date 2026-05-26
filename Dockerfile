FROM node:22-alpine AS frontend-builder

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS api-runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/home/evidencechain/.local/bin:${PATH}"

WORKDIR /app

RUN addgroup --system evidencechain \
    && adduser --system --ingroup evidencechain --home /home/evidencechain evidencechain \
    && mkdir -p /data /app/reports \
    && chown -R evidencechain:evidencechain /app /data /home/evidencechain

COPY requirements.txt pyproject.toml README.md ./
COPY src ./src
COPY scripts/start-api.sh ./scripts/start-api.sh

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir . \
    && chmod +x ./scripts/start-api.sh

USER evidencechain

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3).read()"

CMD ["./scripts/start-api.sh"]

FROM nginxinc/nginx-unprivileged:1.27-alpine AS web-runtime

COPY nginx/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-builder /frontend/dist /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1:8080/healthz >/dev/null || exit 1
