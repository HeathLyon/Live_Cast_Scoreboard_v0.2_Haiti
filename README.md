# Live Cast Scoreboard — 1.1 Control Room release candidate

**Current release:** `1.1.0-rc1`. Existing v0.5 functionality retained, with a protected **Stats & health** dashboard, stable GitHub Pages graphic URLs, separate test/live scoring in production mode, persisted broadcast queue, storage preflight and downloadable database backup.

> **Production candidate, not certified for official results.** Don't use your Render Free instance as a source of truth. The YouTube collector still uses polling; verify actual ingestion and continuity, configure off-server backups, and perform a paid live load test before a 14-day show.

## Fast start on existing Render Free demo

Keep `render.yaml` and all your existing environment variables. Your service remains in `staging` by default. Deploy the latest source, open `/health` (version `1.1.0-rc1`), then open the operator homepage and select **Stats & health**. No change to the existing demo's backend URL is needed.

## Control room operator pages

Open `/` on the operator-only backend. The sidebar includes:

- **Stats & health:** server uptime, DB health, API readiness, YouTube listener, backlog, cast totals, published-graphic readiness and stable links. Readiness is *not* proof that vMix has loaded a URL.
- **Donation data:** full paginated searchable ledger; click a cast card to filter history; open a transaction to view immutable YouTube metadata, override credited USD amount, reassign to a cast, and inspect corrections/audit details. All changes require a reason. No old alert is re-broadcast for a corrected donation.
- **Debug & test events:** simulate one event or a bounded burst, list synthetic events, remove selected ones or clear all tests. Real YouTube records cannot be deleted by test controls. Tests are isolated from production scoring.
- **Graphics Studio:** duplicate a supported template, save a draft, preview, publish, and copy its GitHub Pages/vMix URL without hand-editing code.

Production logins can be named `admin`, `producer` or `viewer` accounts with password hashes configured in a Render secret. Each correction logs the authenticated user. This provides basic password authentication; Google sign-in, sessions/MFA, login rate-limits, and full user administration remain future work.

## New Web Browser URLs for vMix

Use these stable GitHub Pages URLs (no backend parameter):

- **Combined Top 3 + donation**: https://heathlyon.github.io/Live_Cast_Scoreboard_v0.2_Haiti/pages-overlay.html?graphic=top3-alert
- **Goals**: https://heathlyon.github.io/Live_Cast_Scoreboard_v0.2_Haiti/pages-overlay.html?graphic=goals
- **Top 3**: https://heathlyon.github.io/Live_Cast_Scoreboard_v0.2_Haiti/pages-overlay.html?graphic=top3

`js/site-config.js` stores only the PUBLIC backend URL. Update this one file when moving to a paid host. URLs with a legacy `&backend=...` query keep working but remain tied to that hostname.

## Two environments

- `staging` (default): the original demo behavior, mixed real and simulated points, temporary SQLite allowed; broadcast queue optional.
- `production`: only real YouTube paid events count toward on-air rankings/goals and broadcasts; simulated test events can be recorded but not aired; durable filesystem and stronger credentials are required; destructive reset is disabled. Server queue starts paused until the operator enables it.

## Documentation

- [Production deployment runbook](docs/DEPLOY_PRODUCTION.md)
- [Full public case study](docs/PROJECT_CASE_STUDY.md)
- [Short website portfolio description](docs/PORTFOLIO_DESCRIPTION.md)
- [Production Render Blueprint template](render.production.yaml)

## Local development

```bash
pip install -r requirements-dev.txt
python -m pytest -q
python app.py
```

To host a real show, see the runbook before purchasing or connecting a server. This is deliberately a single-node solution (`uvicorn --workers 1`) until the ledger and broadcast queue are migrated to a shared transactional database.
