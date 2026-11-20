# YouTube live paid Super Chat demo — v0.5

**Purpose:** a working demonstration with (1) fake operator-injected donations and (2) genuine paid YouTube chat messages on a public live stream, with the temporary Top 3 and donation alert appearing together in vMix. **This is not an audited or durable competition ledger.**

## 1. Update GitHub and Render

1. Merge the v0.5 pull request in `HeathLyon/Live_Cast_Scoreboard_v0.2_Haiti`.
2. Render Dashboard → `live-cast-scoreboard-demo` → **Manual Deploy → Deploy latest commit** (because `autoDeploy: false`). If using the Blueprint, synchronize the Blueprint after merging.
3. Existing secrets `OPERATOR_PASSWORD` and `VIEW_TOKEN` remain unchanged. Keep `PUBLIC_OVERLAYS=1` and `PAGES_ORIGIN=https://heathlyon.github.io`.
4. In Render → Environment, add **`YOUTUBE_API_KEY`** with your Google Cloud API key. Set `YOUTUBE_MIN_POLL_SECONDS=10` for a short, interactive demo; **return it to 50 seconds or disable the connection afterwards** to avoid quota exhaustion. This is not a production latency solution.
5. Deploy/redeploy and open `https://live-cast-scoreboard-demo.onrender.com/health` to check `version: 0.5.0`. Status reports `youtube_connected: false` until chat has been found and first polling cycle finished.

## 2. Get the API key

1. Go to [Google Cloud Console](https://console.cloud.google.com/), create/select a project, and enable [YouTube Data API v3](https://console.cloud.google.com/apis/library/youtube.googleapis.com).
2. Go to **APIs & Services → Credentials → Create credentials → API key**. Restrict its API permissions to **YouTube Data API v3**. The watcher uses public chat; for this demo it does not require the channel owner's Google account password or an OAuth refresh token.
3. Store the key **only** in Render Environment or a local environment variable. Do not put it in GitHub Pages, JavaScript, a URL, screenshots, messages, or the repository. You can separately run this project locally on your PC; do not run two watchers into the same datastore.
4. If the key is blocked by restrictions or the video is not public / not live, the **YouTube live** tab shows the error. API access and Super Chat availability depend on the channel/stream and YouTube policies.

## 3. Connect a real stream

1. Start a **public YouTube livestream** with live chat enabled and with Super Chat enabled/eligible on the channel. Videos API reports `liveStreamingDetails.activeLiveChatId` **only while currently live**.
2. Open Render operator dashboard (`/`) and sign in as `operator` using `OPERATOR_PASSWORD`.
3. Open **YouTube live** tab → paste `https://www.youtube.com/watch?v=...` → check **Listen for real Super Chats** → Apply.
4. Wait until the status says **listening**. **Events already in chat at first connection are skipped by design**, so connect first and *then* send your test Super Chat.
5. Send a **real purchased Super Chat** with a message such as `#Marcus`. If YouTube reports `USD 5.00`, the scorer awards 5.00 points under the current default multiplier. The YouTube event ID is used to deduplicate repeat reads.
6. Regular messages with `#Marcus` do not award points. Super Stickers (no hashtags) and non-USD events enter the operator's review queue. Ambiguous paid comments also enter review.
7. The existing **Donation simulator** still works. Its events are marked `SIMULATED`; actual YouTube events are marked `REAL YOUTUBE` in Recent Events. **The Top 3 and donation overlay intentionally use combined demo scores**, so DO NOT use them for payouts or a production competition.

## 4. vMix: both graphics only during a donation

Open the [GitHub Pages URL generator](https://heathlyon.github.io/Live_Cast_Scoreboard_v0.2_Haiti/pages-setup.html).

Enter your Render service URL and copy **Synchronized Top 3 and donation alert**. The URL contains `graphic=top3-alert`. For a direct Render input, use `/overlay/top3-alert` with your viewer token.

Add it in vMix as one 1920×1080 Web Browser input. Keep its overlay channel active and set the vMix overlay duration to `0`, so the scoreboard controls the timing. After a USD event is first assigned, both cards appear together and clear after the published **Donation Alert** preset’s duration. Load the browser input before the donation to start with a clean queue.

For a persistent Top 3, uncheck donation-triggered mode in the generator and use the standalone Top 3 and Donation Alert links. Existing `graphic=top3&show=on-donation` links still work for a separate timed Top 3 channel.

## 5. Known limitations before production

- **Temporary data:** Render Free uses ephemeral SQLite and can restart/sleep; lost history means missing/double-counting risks on reconnect. Use PostgreSQL/managed durable database and backups before live scoring.
- **Mixed ranking:** real paid events and simulated events share the demo leaderboard. The operator ledger and history filters distinguish the sources. Reset clears simulated events only. Do not interpret the combined totals as revenue, performance, or competition results.
- **Latency and quota:** This demo uses `liveChatMessages.list`, not YouTube's recommended streaming `streamList`. It respects `pollingIntervalMillis` and a minimum delay. Default minimum 50 seconds is for quota caution, not real-time alerts. For a short demo, use 10–15 seconds; a nonstop 10-second interval can exceed the default YouTube Data API quota (5 units/list call; default 10,000 quota units/day). Production should use streamList with reconnect/backoff.
- **No refund/reversal logic, FX policy, audit-grade records, 24/7 monitoring or historical reconciliation**; this prototype counts USD as paid on the event time and exposes demo totals publicly. Real gifts and Super Stickers are not automatically credited to a cast member.
- **Scope of testing:** tests mock Google HTTP responses and validate local end-to-end scoring, deduplication, source attribution, operator protection and overlay code. No actual YouTube account, stream or payment was accessed in automated tests.

Official API documentation: [Public chat/API-key authorization](https://developers.google.com/youtube/data/live/authentication), [live video chat ID](https://developers.google.com/youtube/data/reference/rest/v3/videos), [liveChatMessages.list](https://developers.google.com/youtube/data/live/reference/rest/v3/liveChatMessages/list), [streamList](https://developers.google.com/youtube/data/live/reference/rest/v3/liveChatMessages/streamList).
