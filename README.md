# Live Cast Scoreboard v0.2 — Haitian flag theme

**An offline-first, bilingual simulation for a YouTube reality-show scoreboard.**

> **NOT FOR LIVE DONATIONS.** This version only accepts simulated test events; it is **not yet connected** to YouTube, Google Sheets, or a durable cloud database. Render testing is optional, and demo records hosted there are temporary. The overlays are deliberately marked `TÈS / DEMO`.

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

Add two **Web Browser** inputs in vMix at **1920×1080**:

| Layer | Local URL |
|---|---|
| Top 3 | `http://127.0.0.1:8000/overlay/top3` |
| Donation alert | `http://127.0.0.1:8000/overlay/alert` |
| Optional full rankings | `http://127.0.0.1:8000/overlay/full` |

The outer page background is transparent. The graphic cards are intentionally opaque enough to read on top of busy video. The `TÈS / DEMO` watermark **must stay during testing**.

### Graphics Studio quick test

From the operator page, choose **Graphics Studio**, edit the Top 3 preset's accent/position/title, select **Save draft**, open the **Draft Preview**, and then **Publish Live**. The existing live overlay should pick up the new settings without being re-added in vMix. The built-in theme keeps Haitian blue/red/white across the shell; you may choose a different accent on individual graphics.

## Optional Render test

Open **[`docs/RENDER_TEST_GUIDE.md`](docs/RENDER_TEST_GUIDE.md)** for exact setup instructions using the included `render.yaml`.

- Local tests: `http://127.0.0.1:8000/` (no cloud account needed).
- Render tests: the same Python app hosted behind a password; staff can open read-only, tokenized producer and vMix links.
- **Important:** Render's default filesystem is ephemeral. Test donations and custom graphics can be lost when the service restarts. Do **not** interpret this as a durable scoreboard or run it as the live show's source of truth.
- Render Blueprints use `render.yaml` to specify a single Starter web service; no extra database or static hosting is required for the demo.

## What is NOT in this release

- Real YouTube Data API authorization or live listener; no real payments counted.
- Google Sheets ledger, reconciliation, FX conversion and operator identity/roles.
- Reliable persistent data on Render (production will use Google Sheets or a proper database).
- Alerts that survive page reload/replay past events, and independent vMix API remote triggering.
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
js/                          Client controls and refresh logic
render.yaml                  Optional protected Render demo deployment
setup_windows.bat            Install Python dependencies on Windows
start_windows.bat            Run local Windows demo
docs/RENDER_TEST_GUIDE.md     Step-by-step cloud test guide
tests/                       Automated test suite
```

## Two-week live production roadmap

After the UI and scoring simulation is approved: (1) Google Cloud OAuth + actual YouTube Super Chat listener; (2) durable Google Sheets ledger and reconciliation; (3) authenticated accounts for staff; (4) operator/producer live presence and recovery monitoring; (5) test against a real channel with producer sign-off before 24/7 operation.
