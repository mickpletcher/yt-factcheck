# EvidenceChain Deployment

This guide covers local Docker, VPS, and cloud deployment.

## Runtime Pieces

- `api`: FastAPI served by Gunicorn with Uvicorn workers.
- `web`: Nginx serving the built React frontend and proxying `/api/` to the API container.
- `evidencechain-data`: SQLite database volume.
- `evidencechain-reports`: exported report volume.

## Secrets

Do not commit `.env`.

Use `.env.local.example` for local testing and `.env.production.example` for deployed systems.

Required live service secrets depend on the providers you choose:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `BRAVE_SEARCH_API_KEY`
- `TAVILY_API_KEY`
- `BING_SEARCH_API_KEY`
- `SERPAPI_API_KEY`
- `API_ACCESS_TOKEN`

For GitHub Actions VPS deployment, configure these repository secrets:

- `VPS_HOST`
- `VPS_USER`
- `VPS_SSH_KEY`
- `VPS_PORT`, optional. Defaults to `22`.
- `VPS_APP_DIR`, optional. Defaults to `/opt/evidencechain`.

## Local Deployment

From the repo root:

```powershell
Copy-Item .env.local.example .env
notepad .env
.\scripts\start-local.ps1
```

Open `http://127.0.0.1:8080`.

Health checks:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/healthz
Invoke-RestMethod http://127.0.0.1:8080/api/v1/health
```

Stop:

```powershell
docker compose down
```

Delete local persistent data:

```powershell
docker compose down -v
```

## VPS Deployment

Install Docker and the Docker Compose plugin on the VPS.

Create the app directory:

```bash
sudo mkdir -p /opt/evidencechain
sudo chown "$USER:$USER" /opt/evidencechain
```

Clone or copy the full repo to `/opt/evidencechain` if the VPS will build images locally.

If the VPS will only pull images from GHCR, copy `docker-compose.yml` and set these environment variables before running Compose:

- `EVIDENCECHAIN_API_IMAGE=ghcr.io/<owner>/<repo>/evidencechain-api:<tag>`
- `EVIDENCECHAIN_WEB_IMAGE=ghcr.io/<owner>/<repo>/evidencechain-web:<tag>`

Create the real environment file:

```bash
cd /opt/evidencechain
cp .env.production.example .env
nano .env
chmod 600 .env
```

Start the stack:

```bash
docker compose up -d
docker compose ps
```

If using GitHub Actions deployment, the workflow copies `docker-compose.yml`, logs in to GHCR, sets the image variables, pulls images, and restarts the stack.

## Cloud Deployment

Use the same two images:

- API image: `ghcr.io/<owner>/<repo>/evidencechain-api:<tag>`
- Web image: `ghcr.io/<owner>/<repo>/evidencechain-web:<tag>`

Recommended cloud settings:

- Put the web container behind the cloud load balancer.
- Keep the API container private.
- Mount persistent storage at `/data` for SQLite.
- Mount persistent storage at `/app/reports` for report exports.
- Store provider keys in the cloud secret manager.
- Set `DATABASE_URL=sqlite+aiosqlite:////data/evidencechain.db`.
- Set `APP_ENV=production`.
- Set `APP_DEBUG=false`.
- Set `API_ACCESS_TOKEN` before public exposure.
- Set `API_RATE_LIMIT_PER_MINUTE` for shared deployments.

For platforms that support only one public container, expose the web image. Keep API access token protection and rate limiting enabled for public or shared deployments.

## Security Hardening

The Compose stack applies:

- Non-root API user.
- Nginx unprivileged image.
- Dropped Linux capabilities.
- `no-new-privileges`.
- Read-only web container filesystem.
- Named volumes for mutable runtime data.
- Nginx security headers.
- Health checks for both containers.

Operational requirements:

- Use HTTPS at the VPS or cloud ingress layer.
- Keep `.env` permissions restricted.
- Rotate API keys if logs, screenshots, or support bundles may have exposed them.
- Back up the `evidencechain-data` volume before upgrades.
- Do not run with `APP_DEBUG=true` in production.

## Updates

Pull and restart:

```bash
cd /opt/evidencechain
docker compose pull
docker compose up -d --remove-orphans
```

Check logs:

```bash
docker compose logs -f web
docker compose logs -f api
```
