# LIVE CAST — MVP Build & Test Plan

**A working scoreboard before show day**  
**Document:** MVP-001 · **Version:** 0.1 (planning draft) · **Prepared:** 19 November 2026  
**Status:** Acceptance criteria and build sequence; implementation not yet started

> **MVP promise:** A valid paid Super Chat containing exactly one cast hashtag increases that cast member's score; the producer scoreboard and vMix Top 3 update; an automatic on-air alert states the recipient's **updated total points and current overall position**. The operator uses English; broadcast and producers use Haitian Creole, subject to native review.

## 1. What we are testing

The core risk is not rendering a leaderboard. It is consistently ingesting YouTube money events for **336 continuous hours**, assigning them correctly, storing each event once, and pushing verified totals to viewers and operators without interruption.

**Launch path:** simulated data → private test YouTube stream → vMix rehearsal → one-day unattended soak → go/no-go review → broadcast.

## 2. MVP included versus deferred

| Included in MVP | Deferred until after MVP passes |
|---|---|
| One active YouTube channel and automatically discovered live chat | Multiple YouTube channels |
| Detect paid Super Chats; record Super Stickers as unassigned | Auto-attributing stickers via a viewer team preference |
| Exact cast hashtag parsing, one hashtag / one assignment | Natural-language or AI guessing |
| Google Sheets ledger + duplicate protection | PostgreSQL/high-availability cluster |
| USD scoring, default $1=1 pt, editable for future events | Complex tier multipliers; retroactive scoring by default |
| English operator status/assignment queue | Full custom administrator suite |
| Haitian Creole read-only producer rankings | Full multilingual content management |
| Live transparent Top 3 browser input | Full drag-and-drop graphics editor |
| Donation alert: earned, updated total, overall rank | Animation marketplace / custom YouTube stickers |
| Template color, title, duration, preview/publish | Arbitrary new layouts from scratch |
| Reconnect status, replay, log and manual export | Geographic redundancy and SLA guarantees |

**MVP boundary:** We can add/duplicate and restyle *supported graphic templates* during the show. Free-form scene editing is a later project. This boundary prevents an attractive editor from delaying a reliable listener.

## 3. User journeys

**Viewer:** Sends USD $20 Super Chat `Cheering for #Marcus`. The show credits Marcus +20.00 points and displays `MARCUS / +20.00 / NEW TOTAL 120.00 / RANK #4` in a short alert, even though Marcus is outside Top 3.

**Producer:** Opens the Kreyòl read-only scoreboard on a phone; sees the same score revision and a visible connectivity/freshness indicator.

**Operator:** Opens an English dashboard, sees a $10 Super Sticker in the unassigned queue, assigns it to Avery with a reason, and verifies the live graphic updates. Operator edits a donation-alert theme in preview, then publishes it without reloading vMix.

**Overnight operator:** Sees connection status, last durable event time, pending reviews, and a clear warning if YouTube or Sheets is degraded; can hand off an accurate shift report.

## 4. MVP screens and graphics

| Screen | Minimum fields / controls |
|---|---|
| `/operator` — English | Live state; Top 3; all-cast ranks; unassigned count; recent events; reassign; simulate event (test mode only); current scoring multiplier |
| `/producers` — Kreyòl | Top 3; full standings; total gross purchased; current point multiplier; last update; connection status; no editing |
| `/graphics` — English | Template library; editable title/color/size/duration; preview/publish; clear PREVIEW/LIVE distinction |
| `/overlay/top3` — Kreyòl | Rank 1–3, cast names, point totals; transparent background; stale-data state |
| `/overlay/alert` — Kreyòl | Cast member, points just earned, **new total**, **overall rank**; 5–7-second timed display; one alert at a time |

**Design rule:** No viewer-provided message text automatically goes on air in MVP. This avoids unscreened language appearing on the live broadcast. Viewer handle is optional, subject to production policy.

## 5. Simulation fixtures — minimum reproducible set

Initial standings for test: Marcus 100.00, Avery 90.00, Jordan 80.00, Taylor 70.00 (all fictitious). Currency is USD unless specified.

| ID | Event | Expected result |
|---|---|---|
| T01 | `$20`, `Go #Marcus!`, Super Chat | Marcus = 120; rank 1; one alert |
| T02 | `$30`, `#Taylor`, Super Chat | Taylor = 100; new rank calculated; alert shows overall rank |
| T03 | `$10`, `#Marcus #Avery`, Super Chat | Queue; no cast score change |
| T04 | `$5`, `hello`, Super Chat | Queue; no cast score change |
| T05 | `$10`, `#Marcus`, ordinary free chat | No points, no donation alert |
| T06 | `$15`, Super Sticker | Queue; no score until manual assignment |
| T07 | Replay T01 with same YouTube event ID | No second ledger credit or alert |
| T08 | `$2.50`, `#mArCuS`, Super Chat | Marcus +2.50; case-insensitive matching |
| T09 | `$10`, `#Marcus123`, Super Chat | No match; queue |
| T10 | `€10`, `#Marcus`, Super Chat | Retain original EUR record; queue currency review |
| T11 | Change multiplier 1 → 10; next `$5 #Avery` | New event grants 50 points; old events unchanged |
| T12 | Kill API connection and resume on startup | No duplicate scores; reconnect and health visible |
| T13 | Sheets write returns timeout/429 | No unconfirmed update shown; retry/inspect and recover |
| T14 | Publish a new alert template | Live display changes without vMix reload |
| T15 | Producer website on mobile + vMix desktop | Same authoritative revision and totals |
| T16 | Two paid events arrive within a second | Both counted once; alerts queued serially |

**Ranking note:** Tests must assert the entire sorted order, not assume Taylor's rank is unchanged. Tie policy and foreign-currency policy require producer approval before real money is scored.

## 6. Build steps and tangible deliverables

### Sprint 0 — Accounts and production inputs

**Build:** Create a private GitHub repo, a paid always-on Render web service, a Google Cloud project with YouTube Data API and Sheets API enabled, and one private test spreadsheet. Obtain authorization from the show's channel owner only for the test account. Register a mock cast roster with hashtags.

**Deliverable:** documented `.env.example` without actual secrets; accessible Render `/health`; spreadsheet tabs created; approved test operator account. **Gate:** no secret appears in GitHub Pages, repository commits, screenshots, or browser network responses.

### Sprint 1 — Offline simulation + scoring

**Build:** Implement normalized hashtag parser, Decimal points engine, ranking/tie rules, event IDs, simulated paid-event generator, and Sheet writer. Use *synthetic* viewer/channel IDs; no YouTube credentials needed.

**Deliverable:** repeatable unit tests, synthetic donations sheet and CLI test command. **Gate:** T01–T11 pass with every event stored once and no accidental score on free chat.

### Sprint 2 — Producer display + vMix graphics

**Build:** GitHub Pages English operator interface and Haitian Creole read-only producer page. Add transparent `top3` and `alert` pages. Render serves score JSON and SSE; browser reconnects and fetches a snapshot after gaps.

**Deliverable:** vMix scene with two Web Browser inputs, plus a mobile producer test link. **Gate:** T14–T16 pass; alert always shows recipient **total and overall position**; no browser reload required.

### Sprint 3 — YouTube connection

**Build:** OAuth authorization; active broadcast discovery; `streamList` consumer; event type filtering; stored cursor; reconnection and duplicate replay. Protect the backend from multi-worker startup. Test on an authorized non-public or test live broadcast with Super Chat enabled, where feasible.

**Deliverable:** real listener status panel and audited live-event ingest. **Gate:** first real test purchase matches YouTube amount/currency, one ledger event, one correct score update and one vMix alert.

### Sprint 4 — Producer intervention + graphics templates

**Build:** unassigned queue, manual assignment with actor/reason, score multiplier setting with future-only versioning, and theme/template preview/publish workflow. Enforce authentication and role checks on all mutation routes.

**Deliverable:** usable English operator console, publishable Haitian Creole templates. **Gate:** every edit is auditable and T03/T06/T11/T14 pass through the actual UI.

### Sprint 5 — Overnight rehearsal + freeze

**Build:** monitoring and restart alerts; last-verified timestamps; backup export; basic runbook. Rehearse channel changes, reconnect, live Sheet failure, and delayed alerts. Freeze tested Render revision and disable automatic deployment before airtime.

**Deliverable:** sign-off packet with measured latency, event count reconciliation, manual fallback graphic and designated responder. **Gate:** complete a 24-hour unattended rehearsal if the production calendar allows; no unexplained score drift, no unrecoverable events, and alerts reach the operator on failure.

## 7. Release gates — measurable definition of done

- [ ] **Correctness:** 100% of 16 documented simulation fixtures pass; repeated event IDs never increase totals.
- [ ] **Persistence:** Scores survive an application restart and reconstruct from the private sheet.
- [ ] **Display:** The Top 3 matches backend ordering; every assigned donation alert shows `earned`, `new total`, `overall rank`.
- [ ] **Presentation:** English operator and Haitian Creole producer/on-air labels are checked by the designated native speaker.
- [ ] **Security:** Only signed-in, authorized staff can access the producer data and edit settings; no secrets appear in GitHub Pages.
- [ ] **Freshness:** Post-persistence backend-to-screen updates meet the target of ≤2 s p95 in a controlled rehearsal; YouTube delivery latency is measured separately.
- [ ] **Recovery:** Forced disconnect, revoked/expired token, Sheet 429 and duplicate replay create visible errors, not fabricated or double scores.
- [ ] **vMix:** Both transparent browser inputs render cleanly on the real vMix machine for 1920×1080 and the selected program frame rate.
- [ ] **Operations:** Named shift owner, alert target, backups, manual fallback and safe deployment policy exist.
- [ ] **Finance:** Showrunners approve point multiplier, USD conversion rules, tie rule, sticker allocation, and prize-related accuracy expectations.

**No-go conditions:** unverified writes alter scoreboards; duplicate event creates extra points; producer data is publicly accessible without approval; on-air alerts omit overall rank or updated total; a failure is invisible to the overnight operator.

## 8. Go-live operating procedure

**Before stream:** confirm YouTube channel login authorization; event source and active chat; cast hashtags; score rule; Kreyòl proofread; graphics preview; vMix input visibility; Render health; Sheet API access and backups. Run one synthetic event in test mode and reset test state before airtime.

**During stream:** watch a concise connection monitor; investigate unassigned events; check ledger write lag; refrain from code deployments; use operator template preview before publishing live graphics. If Sheets becomes unavailable, hold unconfirmed score changes and show a stale/paused indicator.

**At shift change:** export current totals, capture last durable YouTube ID and listener health, note pending reviews, disclose any adjusted donations, and confirm who will respond to alerts.

**After stream:** reconcile with YouTube event records where available, export final ledger, apply retention/data-deletion policy, and produce an approved result report. Do not interpret gross purchases as actual net channel payout.

## 9. Current cost and upgrade decision

| Infrastructure | MVP planning estimate | Watch item |
|---|---|---|
| Single Render paid Web Service | ~$7/mo baseline | 512 MB class; single-process availability |
| Google Sheets | No separate database hosting fee | API quotas, no transactions/uniqueness |
| GitHub Pages | No additional static hosting fee | Public static code; API-based privacy |
| Monitoring / domain / backups | Variable | Budget before production |

These are **planning figures**, not a supplier quote. Under heavy donation load, high-stakes prize rules, or failed recovery tests, upgrade to a transactional PostgreSQL database and consider a separate background worker before live production.

## 10. Approvals still needed

| Question | Owner | Required before |
|---|---|---|
| Cast roster, hashtags and branding | Showrunner | Sprint 2 |
| Confirm Haitian Creole (not French); text reviewer | Production | Sprint 2 |
| Authorized YouTube account + Super Chat eligibility | Channel owner | Sprint 3 |
| Scoring/ties/foreign currency/sticker rules | Showrunner | Real purchase tests |
| Production security and public scoreboard policy | Producer + technical lead | Publishing site |
| vMix overlay placement and approved graphics style | Director / graphics operator | Sprint 2 |
| Shift contacts and monitoring destination | Technical producer | Sprint 5 |
| Data retention, terms and prize-rule compliance | Production/legal | Go-live |

## 11. Official reference links

- YouTube live chat stream: https://developers.google.com/youtube/data/live/reference/rest/v3/liveChatMessages/streamList
- YouTube Super Chat event fields: https://developers.google.com/youtube/data/live/reference/rest/v3/liveChatMessages
- Google Sheets limits: https://developers.google.com/workspace/sheets/api/limits
- Render web services: https://render.com/docs/web-services
- vMix Web Browser: https://www.vmix.com/help29/WebBrowser.html

---

**Next action:** Approve the MVP boundary, then build Sprint 1 against simulation fixtures before connecting the production YouTube channel.
