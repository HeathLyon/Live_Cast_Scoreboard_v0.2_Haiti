# LIVE CAST — Development Specification

**YouTube Super Chat scoreboard + bilingual vMix graphics**  
**Document:** DEV-001 · **Version:** 0.1 (planning draft) · **Prepared:** 19 November 2026  
**Status:** Design baseline; not an implemented or validated application

> **Design intent:** Run an unattended YouTube Super Chat listener for a 14-day / 336-hour reality show. Credit a paid Super Chat to a cast member when it includes exactly one registered `#CastHashtag`. Show the recipient's updated **total points and current rank** in an on-air alert, keep a **Top 3** overlay current, and provide a Kreyòl ayisyen producer scoreboard and an English operator console. Enable new on-air graphics through reusable, editable templates.

## 1. Decisions and assumptions

| Item | Working decision | Status |
|---|---|---|
| Broadcast duration | 24/7 for 14 days (336 hours) | Confirmed planning constraint |
| Broadcast structure | One YouTube broadcast by default; support changing to another live chat | Provisional |
| Paid events | Super Chats and Super Stickers | Confirmed |
| Assignment | Single registered cast hashtag in **paid Super Chat** message | Confirmed design |
| Stickers | Unassigned by default; producer may assign | Working rule |
| Scoring | 1 USD = 1 point; fractional points supported | Default, editable |
| Language | Operator: English; broadcast and producer scoreboard: Haitian Creole | Proposed; native review required |
| Interface hosting | GitHub Pages static HTML/CSS/JS | Working decision |
| Live backend | One paid Render Web Service, Python / FastAPI | Working decision |
| Data store | Private Google Sheet via Sheets API | MVP compromise; load test required |
| Graphics | Persistent Top 3 + auto alerts, then editable template library | MVP + later phases |

**Not yet authorized:** access to the actual YouTube channel, cast roster, finalized show title/branding, live financial rules, donor-name display consent policy, or direct vMix API control. Development must begin with simulated events.

## 2. Functional scope

The system shall: (a) discover or accept the active YouTube broadcast; (b) listen to paid chat events; (c) deduplicate by source event ID; (d) parse exact registered hashtags; (e) persist monetary event and assignment records; (f) calculate point totals and deterministic ranks; (g) update remote displays without refreshing; (h) show a recipient alert containing **points received, new total, and overall rank**; (i) display the current Top 3; (j) offer producer review/correction; (k) maintain separate English and Haitian Creole presentation layers; and (l) allow operators to preview and publish changes to prebuilt graphics templates while live.

**Not required in the first release:** arbitrary drag-and-drop layout builder, automatic video production control, custom YouTube Super Stickers, audience voting from free chat, automated sticker-to-cast attribution, YouTube revenue settlement, and multi-channel/multi-show tenancy.

## 3. Reference architecture

```text
YouTube Live Chat API (active liveChatId)
    | streamList (server stream + resume token)
    v
Render Web Service -- single Python process / one active listener
    |  event classifier -> hashtag parser -> USD point engine
    |  Sheets write + verification -> recompute scoreboard
    |  REST + Server-Sent Events (SSE) -> client updates
    v
Private Google Sheets ledger (cast, donations, assignments, settings, graphics)
    ^
    |
GitHub Pages (static clients; secrets never included)
    |-- /operator       English; auth required; controls and review queue
    |-- /producers      Kreyòl; authenticated live scores
    |-- /overlay/top3   Transparent HTML; data-only
    |-- /overlay/alert  Transparent HTML; timed alert queue
    `-- /graphics       Edit, preview, publish supported templates

vMix on production LAN loads the overlay URLs as Web Browser inputs.
```

**Deployment constraint:** The $7-class Render plan is a single small instance, not guaranteed high availability. Run **one** process owning the YouTube listener; do not start listener code once per Uvicorn/Gunicorn worker. Avoid multi-instance autoscaling and overlapping deploys without a distributed lease. Render app filesystem is ephemeral; do not keep the only state on local disk.

**Live update transport:** Prefer authenticated SSE for server → browser score and graphics-state events. Browsers reconnect and fetch a full snapshot if sequence IDs skip. Use REST for writes, including manual assignment and graphic publishing. WebSocket is optional, not required.

## 4. YouTube ingestion

1. Use Google's OAuth 2.0 authorization with the show's channel owner and the narrowest working scope (typically `youtube.readonly`). Obtain an offline refresh token through the authorized flow; encrypt it as a Render secret. Do not commit it to GitHub or expose it to any web page.
2. Resolve `liveBroadcasts.list(mine=true, broadcastStatus=active, part=snippet,status)` and use `snippet.liveChatId`; also support a manually selected broadcast ID and a non-disruptive handoff when the active chat changes.
3. Connect to `liveChatMessages.streamList` with `part=id,snippet,authorDetails`. Record the last confirmed `nextPageToken`. On interruption, reconnect with a saved token, exponential backoff and jitter. Respect authorization, chat-ended, quota, and disabled-chat errors.
4. Accept `superChatEvent` and `superStickerEvent`. For Super Chat, obtain `snippet.superChatDetails.userComment`, `amountMicros`, `currency`. For Sticker, obtain `snippet.superStickerDetails.amountMicros` and `currency`; no written hashtag is present.
5. Save received records durably before publishing new totals or advancing the **durable** checkpoint. On ambiguous Sheets response, reread the event IDs before retrying. On restart, rebuild known IDs and scores from the ledger; replay from the durable token and deduplicate.
6. After a broadcast, reconcile against `superChatEvents.list` (previous 30 days, channel-owner permission) as an operational check; its record shape differs from live chat events. Do not claim that this is a payment-settlement or refund feed.

**Listener states:** `STARTING`, `CONNECTED`, `RECONNECTING`, `NO_LIVE_CHAT`, `AUTH_REQUIRED`, `RATE_LIMITED`, `STORAGE_DEGRADED`, `ERROR`. Expose last successful API response, last durable event, event rate, reconnection count, and pending review count. A quiet chat should not automatically be marked offline.

## 5. Hashtag assignment and scoring

**Parsing rules**

- Each cast member has one canonical hashtag and optional, unique aliases; validate uniqueness when saving the cast roster.
- Normalize using Unicode NFKC and case-folding. Match complete hashtag tokens only (`#Marcus` matches, `#Marcus123` does not); retain raw original message for authorized review.
- Exactly one distinct cast member matched → `ASSIGNED_AUTO`. Two or more distinct matches → `UNASSIGNED_AMBIGUOUS`. None → `UNASSIGNED_NO_TAG`. An unknown tag does not create a cast member.
- Ignore ordinary `textMessageEvent` for money scoring. Show it only if a future, separately approved non-monetary feature is implemented.
- Super Stickers → `UNASSIGNED_STICKER` until an authorized producer acts. No inferred team from sticker artwork.
- Sanitise donor-generated message text and cap display length. MVP on-air alerts show only approved cast name and score fields, not arbitrary donor text.

**Score rules and accounting**

- Store original purchase as **integer micros** plus ISO 4217 currency. Keep points as decimal numbers (Decimal type), not binary floating point.
- Default: `points = USD purchase amount × 1.00`; e.g., USD 12.50 yields 12.50 points. Display to 2 decimals unless the producers approve another policy.
- For MVP, **non-USD paid events are stored and flagged for currency review**; do not treat EUR 10 as USD 10. Before launch either approve a fixed conversion policy with stored rate/source/timestamp or define an explicit manual review procedure.
- Store `scoring_rule_version` and `points_awarded` per assignment. Changing the multiplier defaults to **future events only**. Recalculation of past points is a separate guarded operation requiring an admin approval and a preview.
- Define ties deterministically: higher points first; if tied, the cast member who reached that total first ranks higher; if still tied, stable cast ID. Confirm tie policy with showrunners.
- Super purchases are **gross viewer-spend events**, not guaranteed channel payout or net donations. Label the on-air currency/points accordingly.

## 6. Google Sheets ledger

Create one private spreadsheet (service account has edit access). **Never let the browser write directly to Sheets.** Use the Render backend as the only writer.

| Tab | Key columns | Mutability |
|---|---|---|
| `Cast` | `cast_id`, `name`, `hashtag`, `aliases_json`, `active`, `image_url` | Admin-managed |
| `Donations` | `event_key`, `broadcast_id`, `event_id`, `received_at`, `viewer_channel_id`, `viewer_name`, `event_type`, `amount_micros`, `currency`, `comment`, `write_status` | Append only |
| `Assignments` | `event_key`, `cast_id`, `status`, `points_awarded`, `rule_version`, `updated_at` | API only; audited |
| `AssignmentAudit` | `audit_id`, `event_key`, `old_cast_id`, `new_cast_id`, `actor`, `reason`, `timestamp` | Append only |
| `Settings` | `key`, `value`, `version`, `edited_by`, `updated_at` | Admin-managed via API |
| `Graphics` | `graphic_id`, `type`, `draft_json`, `published_json`, `version`, `updated_at` | Admin-managed via API |
| `Runtime` | `key`, `value`, `updated_at` (e.g. resume cursor, broadcast ID) | Listener only |

**Consistency model:** Sheets has API quotas but no relational uniqueness constraint. On boot, load the complete event-key index; operate as a **single writer**; before any retry, verify whether an uncertain write already landed; periodically scan for duplicates and raise an error instead of silently changing totals. Never publish a score update until the necessary Sheets write is confirmed. Save resume cursor after confirmed event batches. Batch writes with short intervals if needed, but document that buffering increases the crash-loss window; use replay and reconciliation to recover.

**Performance target:** 60 reads/minute/user/project and 60 writes/minute/user/project are published limits; batch requests count as one request. Model at least 100 paid events/minute as a synthetic spike, and pause automatic scoring if write lag exceeds safe thresholds. A high-volume or prize-critical show should graduate to PostgreSQL.

## 7. Live API contract (planned)

All endpoints are HTTPS; operator and producer APIs require authentication and server-side role checks.

| Endpoint | Method | Result / action |
|---|---|---|
| `/api/v1/health` | GET | Liveness only; no secret data |
| `/api/v1/status` | GET | Authenticated listener state, freshness, current broadcast |
| `/api/v1/scores` | GET | Current scores, ranks, totals, revision number |
| `/api/v1/events?status=unassigned` | GET | Producer review queue |
| `/api/v1/events/{id}/assign` | POST | Assign event; reason + expected revision |
| `/api/v1/settings/scoring` | PATCH | Set future point multiplier; admin role |
| `/api/v1/graphics` | GET | Template library and draft/published state |
| `/api/v1/graphics/{id}/publish` | POST | Publish validated version; operator role |
| `/api/v1/graphics/{id}/preview` | GET | Non-live preview representation |
| `/api/v1/stream` | GET (SSE) | Score/status/graphics update events with event IDs |

Example score snapshot:

```json
{
  "revision": 184,
  "broadcast_id": "example-broadcast",
  "language": "neutral",
  "scoring": {"currency": "USD", "points_per_usd": "1.00", "version": 1},
  "top3": [
    {"cast_id": "cast-a", "display_name": "Marcus", "rank": 1,
     "points": "1250.00"}
  ],
  "unassigned_count": 3,
  "updated_at": "2026-11-19T18:00:00Z"
}
```

An accepted donation creates **one** deduplicated alert event: `{event_key, cast_id, display_name, delta_points, new_total_points, new_rank, score_revision}`. Its `event_key` is used to suppress duplicate animations after SSE reconnects. Rank includes all active cast members, not only the Top 3.

## 8. Graphics and vMix behavior

**Inputs:** Create two stable transparent browser pages: `Top3` and `DonationAlert` (plus an optional `FullScreen`). Load them through vMix **Add Input → Web Browser** at the configured production frame size, typically 1920×1080. Use CSS transparent body/background and safe-area positioning. Do not assume mobile browser behavior matches vMix's embedded Chromium; rehearse on the vMix computer.

**Top 3:** Always display three highest-ranked *active* contestants or fewer if roster is smaller; update after confirmed score revision; animate reorder gently; display per-cast points and numeric rank. Honor a local stale-data indicator rather than displaying fabricated zeros after disconnection.

**Donation alert:** Every newly **assigned** paid event queues an alert containing cast name, points just earned, cast member's **new running total**, and **overall rank**. A contestant ranked 9th still gets an alert marked `#9`. Show 5–7 seconds, then transition out. Do not overlap successive alerts. Handle a bulk backlog after reconnect with an operator-configurable catch-up policy (e.g., suppress old alerts while retaining correct totals).

**Graphics Studio (template MVP):** Define reusable `top3`, `cast_spotlight`, `donation_alert`, and `announcement` templates. Operator can duplicate a template and change text labels, image, color, alignment preset, size preset, duration, language and visibility. Draft changes show in **Preview**; only `Publish` updates the live graphic. Store template configurations as data in Sheets. Truly arbitrary positioning/drag-and-drop belongs to a later release, not the MVP.

**Optional vMix commands (later):** A local bridge running on the vMix LAN can accept authenticated cues and invoke the vMix HTTP API (`OverlayInput1In`, `OverlayInput1Out`). Never expose port 8088 to the internet. The base MVP does not require this bridge: the operator can take graphics on/off through vMix itself while the browser contents update live.

## 9. Bilingual experience

| Audience | Language | Contents |
|---|---|---|
| Primary operator | English (`en`) | Controls, warnings, settings, logs |
| Producers/showrunners | Haitian Creole (`ht`) | Ranked leaderboard, totals, statuses |
| Broadcast viewers | Haitian Creole (`ht`) | Top 3, donation alerts, generic labels |

Text resides in `/locales/en.json` and `/locales/ht.json`. No translation is stored inside numeric event records. Cast names and hashtags retain approved spelling. Ensure accents, fonts, currency formatting and line wrapping work at 1920×1080 and narrow mobile widths. **Native-speaker review is mandatory before broadcast**, particularly for production terminology. Suggested draft labels: `Top 3 → 3 premye yo`, `Points → Pwen`, `Current rank → Pozisyon aktyèl`, `New total → Nouvo total`.

## 10. Security, privacy and resilience

- GitHub Pages files are public static assets; a private GitHub repository does **not** make the published site private. Restrict producer data behind the Render API with login + server-side authorization, CORS allow-list and short-lived sessions. No OAuth tokens, service-account JSON, API admin secrets or donor rows in the static repository.
- For vMix, choose explicitly whether the **score-only overlay** is public (acceptable only with production approval) or uses a protected access mechanism. Never expose private donor data on that endpoint.
- Roles: `admin` (settings/roster), `operator` (graphics and review), `producer` (score/read-only or review, as designated). Audit every edit, publish, correction and scoring-rule change.
- Protect against HTML/script injection in viewer names/messages, cross-site request forgery for session endpoints, and oversized event payloads.
- Keep YouTube API data only as permitted by YouTube's Developer Policies. Implement expiry/refresh or deletion for stored viewer-identifying fields, user deletion requests and authorization revocation. Verify detailed compliance requirements with the production account owner before launch.
- On Sheets/API failure: mark scores stale, buffer only bounded amounts, reprocess from persisted cursor on recovery, and disable automatic on-air alerts rather than showing unverified points. Include an offline/manual vMix fallback still image.
- Set explicit backup/export and recovery procedures; take at least a daily secured ledger export; a Google Sheet is not a transactional database and cannot provide exactly-once guarantees on its own.

## 11. Repository layout and runtime configuration

```text
live-cast/
  backend/
    app/main.py              # FastAPI application and lifespan
    app/youtube.py           # OAuth, active broadcast, streamList
    app/parser.py            # Hashtag matching
    app/scoring.py           # Decimal points + rank computation
    app/sheets_store.py      # Single-writer ledger and dedupe
    app/graphics.py          # Template publishing + alert queue
    app/stream.py            # SSE events and status
    tests/                    # Fixtures, parser/scoring, API tests
    requirements.txt
  site/
    index.html
    operator.html
    producers.html
    graphics.html
    overlay/top3.html
    overlay/alert.html
    css/site.css
    js/api.js
    js/i18n.js
    js/scoreboard.js
    locales/en.json
    locales/ht.json
  docs/
    DEV_SPEC.md
    MVP_PLAN.md
  .github/workflows/
```

Configuration keys (never include secret values in commits): `YOUTUBE_OAUTH_CLIENT_ID`, `YOUTUBE_OAUTH_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`, `YOUTUBE_CHANNEL_ID`, `GOOGLE_SHEETS_ID`, `GOOGLE_SERVICE_ACCOUNT_JSON`, `SESSION_SECRET`, `CORS_ORIGINS`, `SHOW_ID`, `APP_ENV`.

Render launch: Python version pinned, run command `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1` (from backend root), health endpoint configured, paid always-on instance, auto-deploy disabled before show start. Validate all env vars at startup and do not log secrets.

## 12. Validation and operations

| Test class | Evidence to capture | Pass condition |
|---|---|---|
| Parser unit tests | Valid, unknown, duplicate, mixed-case, multi-hashtag | Never auto-credit ambiguous or free events |
| Event dedupe | Replay same `event_id` 10 times | Exactly one ledger event and one on-air alert |
| Scoring | USD 12.50 at multiplier 1.00; update to 10.00 | Old points remain unchanged by default; new points use new rule |
| Queue/review | Unassigned Sticker, unknown tag; manual assign | Audit created; totals and rank recalculate |
| Ranking | Top 3 change; rank #9 donation; tie case | Both displayed totals and global rank correct |
| Live graphics | Draft edit, preview, publish while vMix stays loaded | No refresh or service restart required |
| Language | English operator, Kreyòl producers + vMix | Consistent scores, no missing translations |
| Recovery | Kill listener, restart, resend old messages | No duplicated totals; status visible; cursor recovery tested |
| Storage failure | Induce Sheets 429/timeout | No unconfirmed score published; recovery explicit |
| Load | Synthetic 100 paid events/minute burst | No lost records; bounded backlog and measurable delay |
| Overnight | 24-hour unattended rehearsal, simulated chat | Health alerts, logs and restart recovery verified |
| Production | One controlled live Super Chat (channel-approved) | Event ID, amount, credit and vMix alert match |

**Latency budget (target, not a YouTube guarantee):** After a received event is confirmed in Sheets, deliver a fresh scoreboard revision to connected clients in **≤2 seconds at p95** during normal load. Track separately the delay from the viewer purchase to API delivery.

**Operations:** Publish an operator runbook with `START`, `STOP`, `SWITCH BROADCAST`, `FREEZE GRAPHICS`, `UNASSIGN/REASSIGN`, `RESTORE`, `EXPORT`, and a shift-handoff checklist. A two-week show must have a named escalation contact, alert channel and daily ledger health review.

## 13. Delivery phases and upgrade gates

**Phase A — offline simulation:** parser, Decimal scoring, Sheets test ledger, mock SSE, static demo Top 3 and alert.  
**Phase B — connected MVP:** OAuth, active chat stream, dedupe, producer review, live vMix browser and Kreyòl dashboard.  
**Phase C — graphics control:** template drafts, preview/publish, manual spotlight, accessibility and language review.  
**Phase D — production-hardening:** 24h soak, monitoring, backups, active broadcast changes, recovery game-day rehearsal.  
**Phase E — optional enhancements:** PostgreSQL migration, multi-host high availability, remote vMix cue bridge, free-chat team selection, true drag/drop scene editor.

**Escalate from Sheets to PostgreSQL if** spikes exceed dependable write throughput; two or more writers are required; scoring controls prizes/eliminations requiring stronger transactional guarantees; or recovery cannot be proven within the available YouTube replay window.

## 14. Open decisions / approval register

1. Show name, branding, cast roster, approved hashtag aliases, and cast pictures.
2. Confirm `ht` (Haitian Creole) rather than French; obtain a bilingual production reviewer.
3. Confirm Super Chat eligibility and actual YouTube channel owner authorization.
4. Determine live stream continuity and the operational procedure when a new broadcast starts.
5. Approve the interpretation of points, tie-breaking, non-USD purchases and sticker allocation.
6. Decide whether on-air leaderboard-only data may be publicly readable.
7. Determine who is permitted to make and approve reassignment and scoring edits.
8. Set alert duration, rank animation, graphics style and mobile producer layout.
9. Set operational alert delivery and shift handoff responsibilities.
10. Approve data retention/privacy and any competition/legal disclosures before launch.

## References — official technical documentation (checked 19 November 2026)

- YouTube `liveChatMessages.streamList`: https://developers.google.com/youtube/data/live/reference/rest/v3/liveChatMessages/streamList
- YouTube live chat event fields: https://developers.google.com/youtube/data/live/reference/rest/v3/liveChatMessages
- YouTube `liveBroadcasts.list`: https://developers.google.com/youtube/data/live/reference/rest/v3/liveBroadcasts/list
- YouTube `superChatEvents.list`: https://developers.google.com/youtube/data/live/reference/rest/v3/superChatEvents/list
- YouTube OAuth: https://developers.google.com/youtube/data/guides/authentication
- YouTube developer policies: https://developers.google.com/youtube/terms/developer-policies/
- Sheets API quotas: https://developers.google.com/workspace/sheets/api/limits
- Render web services: https://render.com/docs/web-services
- Render ephemeral filesystem: https://render.com/docs/disks
- vMix web browser transparency: https://www.vmix.com/help29/WebBrowser.html
- vMix overlay shortcuts: https://www.vmix.com/help29/ShortcutFunctionReference.html

---

**Document control:** This specification represents agreed planning direction with identified assumptions; it is not evidence of integration, testing, legal approval, or production readiness.
