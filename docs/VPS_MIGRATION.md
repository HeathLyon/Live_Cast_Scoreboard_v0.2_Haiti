# Hosting Live Cast on your own VPS

This is an alternative to `render.production.yaml` if you purchase a Linux VPS. **Use a dedicated single-node deployment and test it with a real YouTube stream before any official show.**

## Requirements

- Ubuntu LTS or another supported Linux distribution, current Python and security updates
- DNS hostname (for example, `scoreboard.yourdomain.com`) and HTTPS/TLS certificate
- Storage volume with capacity monitoring and automatic off-server backups
- Firewall allowing inbound HTTPS only; Python listens on localhost
- Restricted operator credentials and YouTube API credentials supplied through a protected environment file

## Deploy

```bash
sudo useradd --system --create-home --home-dir /srv/livecast livecast
sudo mkdir -p /srv/livecast/app /srv/livecast/data /etc/livecast
sudo chown -R livecast:livecast /srv/livecast
sudo chmod 750 /srv/livecast/data
# As the livecast user, check out this repo to /srv/livecast/app.
cd /srv/livecast/app
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Place real secrets in `/etc/livecast/livecast.env`, readable by the service account and system administrators only. Base values on `.env.production.example` and set:

```text
LIVECAST_ENV=production
LIVECAST_REMOTE_TEST=1
LIVECAST_DB=/srv/livecast/data/livecast.sqlite3
LIVECAST_PERSISTENT_ROOT=/srv/livecast/data
LIVECAST_REQUIRE_MOUNT=0
LIVECAST_SERVER_QUEUE=1
LIVECAST_PUBLIC_URL=https://scoreboard.yourdomain.com
LIVECAST_PAGES_URL=https://heathlyon.github.io/Live_Cast_Scoreboard_v0.2_Haiti/
PUBLIC_OVERLAYS=1
PAGES_ORIGIN=https://heathlyon.github.io
```

Add `OPERATOR_PASSWORD`, `VIEW_TOKEN`, `YOUTUBE_API_KEY` as private values. Do not include `.env` in GitHub. Set restrictive ownership/permissions on the file, and use a secrets manager when possible.

Use a systemd service with `WorkingDirectory=/srv/livecast/app`, `User=livecast`, `EnvironmentFile=/etc/livecast/livecast.env`, `ExecStart=/srv/livecast/app/.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8000 --workers 1`, `Restart=always` and `RestartSec=5`. Put Nginx/Caddy with HTTPS in front; pass the original `Host` and `X-Forwarded-Proto` headers. Avoid running a public unauthenticated listener.

## Switching vMix to the new server

Edit the **public hostname only** in `js/site-config.js`, commit the update to GitHub Pages, and retain stable vMix links such as `pages-overlay.html?graphic=top3-alert`. Existing links that explicitly contain `backend=` still point to the old server and need replacement.

## Operations checklist

Verify `/health`, login, `/api/system/status`, YouTube LISTENING, real/test separation, queue controls, and the database-backup download. Restore one backup onto a test machine and validate the donation ledger. Add daily off-server backups, alert monitoring, uptime checks, and post-show reconciliation. A single SQLite node is not redundant: for high availability or horizontal scaling, migrate the ledger and queue to PostgreSQL.
