# Live Cast — Production deployment runbook

**Release:** `v1.1.0-rc1` production foundation. **Not approved for an unattended 14-day live show until the acceptance checklist passes.**

## 1. What is ready, and what is not

The current verified v0.5 demo is preserved as the **staging** profile. This release adds a **production** profile that uses real YouTube events only in public scores; simulations remain visible to the operator but never affect on-air totals. It also adds server-based playback, queue controls, diagnostics, stable GitHub Pages URLs and an on-demand SQLite backup.

This single-node SQLite implementation requires paid, attached persistent disk storage. It does **not** currently implement PostgreSQL, Google OAuth sign-in or multi-factor authentication, off-server automatic backups, guaranteed recovery of YouTube events after long disruptions, rate-limiting, redundant collectors, or streaming `streamList` ingestion. The existing YouTube collector still polls `liveChatMessages.list` and must be tested with the actual broadcast channel. Do not call the system production-verified until those requirements are addressed and signed off.

## 2. Preserve the working demo

1. Export your `/api/export/donations.csv` and download `/api/system/backup.sqlite3` from the operator page.
2. Leave your existing Render Free service and `render.yaml` configured as **staging**; never rely on its ephemeral database for real results.
3. Publish this source through Codex to GitHub `main` after the automated tests pass.

## 3. Buy a server: easiest supported migration path

Use **a separate paid Render web service** with `render.production.yaml` as its Blueprint file (or configure the service and disk manually). This avoids turning your running free demo into production accidentally. The production template uses **one Uvicorn worker** and mounts a persistent disk at `/var/data`.

Add these environment values (Render secret entries are marked `sync: false`):

| Variable | Purpose |
|---|---|
| `LIVECAST_ENV=production` | Separates official scores from test events |
| `LIVECAST_REMOTE_TEST=1` | Keeps the operator API behind authorization |
| `LIVECAST_DB=/var/data/livecast.sqlite3` | Persistent database file |
| `LIVECAST_PERSISTENT_ROOT=/var/data` | Trusted data mount |
| `LIVECAST_REQUIRE_MOUNT=1` | Refuses to start if the expected volume isn't mounted |
| `LIVECAST_SERVER_QUEUE=1` | Server-side alert delivery |
| `PUBLIC_OVERLAYS=1` | Public on-air-only read endpoints |
| `LIVECAST_PUBLIC_URL` | The exact HTTPS address of the paid backend |
| `LIVECAST_PAGES_URL` | GitHub Pages base URL |
| `LIVECAST_USERS_JSON` | Private JSON mapping named users to a role and scrypt password hash |
| `VIEW_TOKEN` | Private read-only token (32+ characters) |
| `YOUTUBE_API_KEY` | Private restricted YouTube Data API key |

The startup checks fail closed if required production settings are absent or weak. A valid mount check is necessary but cannot replace actual durable-storage verification.


### Creating named accounts (without editing code)

Run `python scripts/create_user_hash.py` locally to generate a password hash (never commit the password). In Render's environment settings, create **one secret** `LIVECAST_USERS_JSON` whose value is a JSON object like:

```json
{"director":{"role":"admin","password_hash":"scrypt$16384$8$1$SALT$HASH"},
 "floor_producer":{"role":"producer","password_hash":"scrypt$16384$8$1$SALT$HASH"}}
```

Replace `SALT` and `HASH` with the script output. Each account needs a unique hash and its own password. Roles: admin can operate debug tools/backups; producer can reconcile donations and publish graphics; viewer is read-only. Login uses browser HTTP Basic over HTTPS. This is an interim access system, **not** Google OAuth, and does not yet support MFA or login rate limiting. For multi-person production, add those controls and test account revocation before launch. In production, the shared staging `operator` account is disabled.

## 4. Point existing vMix graphics at the new server

Update the single **public** configuration file `js/site-config.js`:

```javascript
window.LIVECAST_SITE = Object.freeze({
  backendUrl: 'https://YOUR-PAID-SERVER.onrender.com',
  pagesUrl: 'https://heathlyon.github.io/Live_Cast_Scoreboard_v0.2_Haiti/'
});
```

Commit that file; GitHub Pages redeploys automatically. Do **not** add any API keys or passwords to it. Use stable URLs such as:

- Combined Top 3 + alert: `https://heathlyon.github.io/Live_Cast_Scoreboard_v0.2_Haiti/pages-overlay.html?graphic=top3-alert`
- Goals: `https://heathlyon.github.io/Live_Cast_Scoreboard_v0.2_Haiti/pages-overlay.html?graphic=goals`
- Persistent Top 3: `https://heathlyon.github.io/Live_Cast_Scoreboard_v0.2_Haiti/pages-overlay.html?graphic=top3`

Unlike earlier URLs that included `&backend=...`, these **stable URLs** do not need to change when the hostname changes. An old URL containing `backend=` overrides the config: replace that old vMix input once with the stable format.

## 5. Control-room dashboard

Open `/` on your paid service and log in as your named admin or producer account. In **Stats & health** you can see server version, uptime, DB integrity, real/test event counts, YouTube API status, queue size, and clickable/copyable URLs; pause/resume/skip on-air playback; and download a database backup. Queue controls do not modify score totals.

The production queue is initially **paused** to protect against accidental playback. Activate the vMix combined overlay and then click **Resume alerts**. New real paid events will be recorded immediately and shown sequentially. When a burst creates a large backlog, operators can choose **Enable burst grouping**; at 12+ waiting alerts the system summarizes the next 10 in a single on-air card, while all 10 original donation records remain in the ledger. Grouping is OFF by default and should not be used if individual donor acknowledgment is promised. Test donations still go through Donation Simulator, but their points do not appear on the production public rankings.

## 6. Backup and recovery

- Download `api/system/backup.sqlite3` before and after each show segment and copy the file to a secure off-server destination.
- Do not overwrite a running SQLite DB file. To restore, stop the service and replace `/var/data/livecast.sqlite3` with a verified backup, or use a supported maintenance procedure.
- Schedule automatic **off-server** backups before the 14-day event. The on-demand backup button is not a replacement.
- Practice restoring a test backup onto a separate instance and verify rankings, queue and audit history.
- Export donation CSV for transparent reconciliation. Keep a separate record from the YouTube channel for disputes.

## 7. Launch acceptance checklist

- [ ] Paid service stays running and persistent disk survives restart/redeploy.
- [ ] Operator routes require authentication; unauthorized writes return 401.
- [ ] Public read endpoints reveal only broadcast-safe totals.
- [ ] Real YouTube Super Chat with exactly one cast tag is counted once.
- [ ] Simulated Super Chat in production changes **no** public score or on-air alert.
- [ ] 100/500-event burst tests preserve every transaction and queue entry.
- [ ] Combined Top 3 and alert are synchronized in vMix during camera transitions.
- [ ] Pause/resume/skip affects delivery only; scoreboard remains accurate.
- [ ] Explicitly enable and test grouped on-air summaries if permitted by donor acknowledgment rules.
- [ ] Collector reconnect/restart recovery and continuation tokens checked on stream.
- [ ] YouTube polling quota and latency measured under actual stream conditions.
- [ ] Restore test from an independent backup passes.
- [ ] Monitoring and alert escalation assigned to a staff member.
- [ ] Reviewed by producer and a Haitian Creole speaker for final graphic labels.

## 8. Important editing limitations

Original YouTube transaction amount, message, timestamp, currency, ID and source are immutable. A producer can assign/reassign the cast, hold an event for review or override the **credited USD amount** with an explanation. The effective score reflects that adjustment; the original record and every edit are retained in the audit trail. Correcting a transaction cancels any old pending/active animation so it cannot announce stale totals. Already completed broadcast animations cannot be recalled.

Foreign currency correction and entry of entirely missing, manually verified donations need an agreed verification/FX policy and a separate future workflow. A copied graphic inherits the supported type of its source template; this release does not add drag-and-drop graphic creation or a head-to-head battle engine.

## 9. Open production gaps

The release is an **operational production candidate**, not certification that it will run without missed donations for 14 days. Before critical use, implement/verify `liveChatMessages.streamList` and reconnect handling; add external off-server backups, independent reconciliation, Google sign-in/MFA and rate limits, and monitoring. The paid Render single-node pattern cannot be horizontally scaled without moving the queue and ledger to PostgreSQL or another transactional shared store.

## References

- Render persistent disks: https://render.com/docs/disks
- Render Blueprint spec: https://render.com/docs/blueprint-spec
- YouTube `streamList`: https://developers.google.com/youtube/data/live/reference/rest/v3/liveChatMessages/streamList
