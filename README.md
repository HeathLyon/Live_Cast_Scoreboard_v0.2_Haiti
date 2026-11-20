# Live Cast Scoreboard v0.5 — Goals, YouTube and broadcast demo

**A Haitian Creole broadcast graphics demonstration with simulated donations and optional *real paid YouTube live chat* ingestion.**

The **YouTube live** tab connects to a public live stream using a server-side YouTube Data API key. The **Top 3 + donation alert** graphic shows both cards in one vMix input for the duration set in the published Donation Alert preset. The standalone Top 3 stays visible by default. The operator ledger identifies simulated and real events, and the demo standings combine both sources.

**Root-level GitHub layout:** Keep `index.html`, `producer.html`, `overlay.html`, `css/`, and `js/` in the repository root beside `app.py`. No `web/` subfolder is required.

> **DEMO ONLY — NOT FOR OFFICIAL DONATION ACCOUNTING.** This release can observe real paid YouTube chat events when configured but combines them with fabricated test events in the broadcast ranking. Render demo records are temporary, YouTube connection is optional, and Google Sheets / durable cloud database are not connected. `TÈS / DEMO` stays on any displayed graphic.


## NEW v0.5 — Goal progress and retrospective review

- **Goals & ticker tab:** create, edit, delete or disable multiple goals. An operator-only global switch controls whether any goal progress graphic appears on air. Active goals rotate every eight seconds.
- **Five tracking modes:** combined assigned cast points; all USD donations (test + real); *real YouTube* USD donations only; one cast member's points; or manually entered counts such as Gold memberships. Optional countdown, message and sort order.
- New automatic goals may **start from the current total** (count only subsequent donations) or include the full historical demo count. Operators can reset the baseline or apply an audited manual adjustment; this does not alter donor amounts.
- **Scoring & cast tab:** add new cast members with a unique ID, or edit the names, active status and any number of valid comma-separated hashtags (up to 15 per person). Changed tags affect **future** matching; historical donations are left intact.
- **Assignment queue:** unassigned paid events can be credited after the fact. New searchable, paginated history finds older donation events by ID, donor or message and can filter by event source. Edits recalculate cast rankings and goal progress, with an audit record; moving an already-credited donation doesn't create a fake new donation alert.
- Public GitHub Pages goal graphics use the same narrowly scoped read-only API; no private donor messages, passwords or editing endpoints are exposed.

**[Goals, Cast & Review — setup and operating guide](docs/GOALS_CAST_REVIEW.md)**

**Google Sheets is optional for the demo.** The demo stores goals, donations and cast settings together in a single local SQLite file. On Render Free that file is *ephemeral*, so it is not appropriate for prize-sensitive or 14-day uninterrupted scoring. Before production, use a managed durable database (with backups and audit/reconciliation) and optionally export/sync an append-only ledger to Sheets for producer review.

## Setup guide

Follow **[`docs/YOUTUBE_LIVE_DEMO.md`](docs/YOUTUBE_LIVE_DEMO.md)** for the exact Google Cloud API key, Render, YouTube stream, and vMix instructions.

## What you can test today

- Add simulated YouTube Super Chats with cast hashtags such as `#Marcus`.
- Dollar-to-point scoring (default **$1 = 1 point**, editable for subsequent events).
- Exact hashtag matching and review for ambiguous messages; Super Stickers queue for manual assignment.
- Deduplication using the event ID, all-cast ranking, persistent Top 3 graphic, and recipient alerts that show new total **and current rank** even when outside Top 3.
- English operator panel and Haitian Creole producer scoreboard and broadcast overlay.
- Haitian flag palette: **blue #00209F, red #D21034, white #FFFFFF** (with navy panels for contrast).
- Clone graphic templates, edit position, scale, accent and Kreyòl/English titles; save a draft and publish it live.
- Export demo transactions as CSV; SQLite keeps local demo records between launches.
- Remote test in a protected Render web service with a separate read-only display token. Local and Render test instances keep **separate demo data**; they do not synchronize.

## First: run on Windows (recommended)

1. Extract the ZIP so `app.py`, `setup_windows.bat`, and `start_windows.bat` are together in the project folder.
2. Install [Python 3.11+](https://www.python.org/downloads/) if needed. On Windows, check **Add Python to PATH**.
3. Double-click **`setup_windows.bat`** and let dependencies install (the terminal prints the result).
4. Double-click **`start_windows.bat`**; keep the terminal window running.
5. Open `http://127.0.0.1:8000/` (English operator), and `http://127.0.0.1:8000/producers` (Kreyòl producer).
6. In **Donation Simulator**, send `Super Chat`, `USD`, amount `25.00`, and message `#Marcus`.
7. Verify Marcus now has 25.00 points and rank changes correctly. Test `#Marcus #Avery` to see a review item; a Super Sticker should also go to review.
8. Open the URL `http://127.0.0.1:8000/overlay/top3` and watch the Top 3. For an alert, open `http://127.0.0.1:8000/overlay/alert` **before** you trigger another simulated donation.

### Run with vMix on the same Windows PC

For the synchronized cards, add the combined URL as one **1920×1080 Web Browser** input in vMix. For a persistent Top 3, use the standalone Top 3 and Donation Alert inputs.

| Layer | Local URL |
|---|---|
| Top 3 + donation alert | `http://127.0.0.1:8000/overlay/top3-alert` |
| Persistent Top 3 | `http://127.0.0.1:8000/overlay/top3` |
| Donation alert | `http://127.0.0.1:8000/overlay/alert` |
| Optional full rankings | `http://127.0.0.1:8000/overlay/full` |
| Goals lower-third | `http://127.0.0.1:8000/overlay/goals` |

The outer page background is transparent. The graphic cards are intentionally opaque enough to read on top of busy video. The `TÈS / DEMO` watermark **must stay during testing**.

### Graphics Studio quick test

From the operator page, choose **Graphics Studio**, edit the Top 3 preset's accent/position/title, select **Save draft**, open the **Draft Preview**, and then **Publish Live**. The existing live overlay should pick up the new settings without being re-added in vMix. The built-in theme keeps Haitian blue/red/white across the shell; you may choose a different accent on individual graphics.

## Optional Render test

Open **[`docs/RENDER_TEST_GUIDE.md`](docs/RENDER_TEST_GUIDE.md)** for exact setup instructions using the included `render.yaml`.

- Local tests: `http://127.0.0.1:8000/` (no cloud account needed).
- Render tests: the same Python app hosted behind a password; staff can open read-only, tokenized producer and vMix links.
- **Important:** Render's default filesystem is ephemeral. Test donations and custom graphics can be lost when the service restarts. Do **not** interpret this as a durable scoreboard or run it as the live show's source of truth.
- Render Blueprints use `render.yaml` to specify a single **Free** web service; no extra database or static hosting is required for the demo.
- A Free Render service may spin down after 15 minutes without inbound requests, then take time to wake. Demo data on its local SQLite filesystem is not durable; **never use this mode as the source of truth for the 24/7 live show**.

## Demo limitations

- YouTube live chat is available as a non-production demo via a server-side API key; OAuth for nonpublic/owner operations is not included.
- Google Sheets ledger, reconciliation, FX conversion and operator identity/roles.
- Reliable persistent data on Render (production should use a managed database, with optional Google Sheets reporting).
- Durable recovery/replay and reconciled donation alerts; the demo only follows the current public live chat feed.
- Verified production translations (a native Haitian Creole speaker should review all labels).

## Useful commands for developers

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
python -m pytest -q
python app.py                      # local-only, on 127.0.0.1:8000
```

### Project structure

```text
app.py                       FastAPI endpoints and remote-demo access checks
core.py                      Parsing, points, match and rankings
store.py                     Transactional local demo SQLite store
index.html                   English control room
producer.html                Haitian Creole production view
overlay.html                 vMix overlay HTML
css/style.css                Base styles
css/haiti-theme.css          Haitian blue/red/white theme overrides
js/                         Client controls and refresh logic
render.yaml                  Optional protected Render demo deployment
setup_windows.bat            Install Python dependencies on Windows
start_windows.bat            Run local Windows demo
docs/RENDER_TEST_GUIDE.md     Step-by-step cloud test guide
tests/                       Automated test suite
```

## Two-week live production roadmap

After the UI and scoring simulation is approved: (1) production YouTube listener with reconnect/reconciliation; (2) managed durable database and audit export (optional Google Sheets mirror); (3) authenticated accounts for staff; (4) operator/producer live presence and recovery monitoring; (5) test against a real channel with producer sign-off before 24/7 operation.


## GitHub Pages broadcast graphics

Render still calculates scores; GitHub Pages only hosts the static visual pages. The public read-only feed returns **ranks, totals, and alert text only**, never donor messages or the edit API. The operator dashboard continues on Render with Basic authentication.

1. Deploy the patched `app.py` and `render.yaml` to Render. Confirm `/health` reports `public_overlays_enabled: true`. It is intentionally public demo output; do not use for private or prize-sensitive live scoring.
2. Enable GitHub Pages in **Settings → Pages**, source **main**, folder **/(root)**.
3. Open `https://heathlyon.github.io/Live_Cast_Scoreboard_v0.2_Haiti/pages-setup.html` (or the custom Pages origin).
4. Enter only your base Render service URL, e.g. `https://example.onrender.com`, and press **Generate vMix links**. Do not enter your operator password or VIEW_TOKEN.
5. Copy the generated Top 3 and Donation Alert links into separate vMix Web Browser inputs at 1920×1080, then activate both overlays. These links are hosted on **GitHub Pages**.
6. Open the operator dashboard on Render, sign in as `operator`, and simulate `$25 #Marcus`. The Pages graphics poll the read-only Render feed. Keep the alert page open before triggering the donation.

If the URLs show scores but no alert: activate the vMix alert overlay before sending a NEW donation; old alerts do not replay. If pages show no scores, check `/health`, `PUBLIC_OVERLAYS=1`, and your browser's network/CORS messages.

**Important:** The public read-only feed is visible to anyone who knows its URLs. Only **broadcast data** is exposed, and both private operator API and donor transaction details remain protected. Disable the feed in production with `PUBLIC_OVERLAYS=0`. Render Free will sleep and lose ephemeral data; not suitable for a two-week 24/7 live contest.
