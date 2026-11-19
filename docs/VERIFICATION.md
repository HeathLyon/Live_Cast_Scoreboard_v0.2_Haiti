# Updated v0.2 verification

- 27 automated Python tests passed on this v0.2 source (`python -m pytest -q`).
- Remote test access boundary (operator password vs. view-only token) is covered by tests.
- Haitian blue/red/white theme is loaded by all three UI pages.
- Browser-rendered static HTML/JS previews were generated; the overlay outer canvas has transparent alpha.
- Full end-to-end live YouTube and deployed Render tests are NOT performed.

---

# v0.1 verification report

Verified on November 19, 2026, in the build environment (not the user's production equipment).

## Automated backend tests

`python -m pytest -q` — **24 passed**.

Coverage includes exact/case-insensitive hashtag matching, multiple hashtags, non-matching suffixes, free chat ignored, Super Stickers queued, non-USD purchases held, decimal points, unique event ID deduplication, manual assignment, rank outside Top 3, future-only multiplier, graphic draft/publish, graphic clone, cast alias collision rejection, CSV export, reset, and persistence after reinitialization.

## Browser visual checks

Headless Chromium rendered the same HTML/CSS/JS with controlled API fixtures. **No JavaScript page errors** were observed. The code was also checked with `node --check`.

Sample screenshots are in `previews/`:

- `operator.png` — English dashboard, desktop layout
- `producer.png` — Haitian Creole producer view, mobile layout
- `overlay-top3.png` — 1920 × 1080 transparent leaderboard
- `overlay-alert.png` — 1920 × 1080 transparent alert with updated total and rank

Overlay PNG backgrounds were explicitly confirmed to contain alpha transparency (`RGBA`, background alpha `0`).

## Not tested / not complete

- Official live YouTube connection or any real Super Chat purchase
- Google Sheets API integration
- Online deployment, authentication, or remote staff access
- vMix's actual embedded browser; verify on your vMix PC
- 24/7 uptime, Google API quota pressure, failover, and 336-hour production reliability
- Native-speaker translation review

This is an offline simulation first build, **not a ready-to-air 24/7 tracking system**.
