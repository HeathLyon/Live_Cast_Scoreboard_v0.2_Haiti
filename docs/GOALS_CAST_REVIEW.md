# Goals, Cast & Donation Review — v0.5 operator guide

## Status and safety

This build is for **simulation / demonstration only**, including the optional v0.4 YouTube ingestion. Real and synthetic USD transactions **both count toward combined demo goals**. Real-only USD goals track only events recorded with `source=youtube`. They are not payout reconciliation, refunds, FX conversions, membership confirmation, or audited competition results. Render Free SQLite can disappear on restart/sleep/redeploy.

## Add and adjust on-air goals

1. Open the operator dashboard on Render with `operator` and the OPERATOR_PASSWORD.
2. Choose **Goals & ticker**.
3. Enter a URL ID (`goal-4000`), goal title (`4,000 PWEN`), choose a tracking metric, target (`4000`) and an optional countdown end, expressed in the operator browser's local time. Add a short Kreyòl ticker message, if desired.
4. For a new automatic goal, keep **Start counting from now** selected if you want a fresh goal. Uncheck it to include prior demo transactions.
5. Click **Create goal**. Set **Show goals ON AIR** to ON. The goals overlay appears; turn OFF at any time to clear the on-air goal without touching vMix.
6. Use **Edit** for target/title/ticker/countdown/visibility. `Adjustment (+/-)` changes the display-relative total for an automatic goal but does **not** alter donations; `Reset automatic progress baseline` restarts counting from the current total. For `Manual count`, change `Manual current amount` directly (e.g. 12 of 100 memberships).
7. You can create any number of goals. The graphic rotates between enabled goals every eight seconds, ordered by Rotation order. Each has an independent on/off checkbox. Delete a goal if it is no longer needed.

### Goal metric definitions

| Metric | Source | What is counted |
| --- | --- | --- |
| All assigned cast points | Scoring ledger | Sum of awarded USD points across cast; excludes unassigned and unresolved FX |
| All USD donations | Scoring ledger | All USD paid events, assigned or pending; **real + simulated** |
| Real YouTube USD donations | Scoring ledger | All USD paid events recorded by the YouTube listener only, even if unassigned |
| Specific cast member points | Scoring ledger | USD points assigned to the selected member |
| Manual count | Operator | Manually entered current value; for members, other custom targets |

Percent is calculated from current/target and capped at 100% for the progress bar. No FX conversion is performed. Goal creation and edits are audited in the demo's SQLite file.

## Add cast and hashtags

1. Choose **Scoring & cast**.
2. For a new cast member enter a unique lowercase ID (e.g. `new-cast`), their display name, and comma-separated hashtags such as `NewCast, TeamNewCast`.
3. Press **Save cast member**. To edit an existing member, click **Edit** next to that member, change the display name/tags or Active checkbox and save.
4. Tag matching is case-insensitive, exact and requires one unique, one-word hashtag. No tag may belong to two members. Names and tag lists are editable; cast IDs are stable references in donation history.
5. Tag edits affect **new** incoming events. Older unmatched donations require manual review rather than retroactive automatic reassignment.

## Assign a paid donation after the fact

1. Open **Assignment queue** to see new unassigned/ambiguous USD paid Super Chats and Super Stickers.
2. For events older than the first 80 visible in the main queue, use **Search donation history**, filter to Unassigned, optionally select Real YouTube as the source, enter donor name, hashtag text or event ID and click Search history. It searches the entire local demo ledger, 50 rows per page.
3. Choose a cast member, enter a substantive reason (e.g. `Producer reviewed donor message`), and select **Assign**. The donor amount is recorded only once; rankings and goal metrics update immediately. The assignment creates a new alert once for previously pending USD events.
4. To correct an already-assigned USD event, choose All donations or Already assigned and search. Select a different cast and **Correct**. This moves the credited points, records an audit trail, and doesn't generate a misleading second donation alert.
5. **Non-USD paid events** remain in FX review and cannot be credited to a cast until a formal exchange-rate policy exists. Free chat never adds points. Duplicate YouTube message IDs are ignored by the scorer.

## GitHub Pages goal graphic URLs

The URL generator at:

`https://heathlyon.github.io/Live_Cast_Scoreboard_v0.2_Haiti/pages-setup.html`

Now includes **Goals progress bar**. For the existing Render hostname, the goal URL is:

`https://heathlyon.github.io/Live_Cast_Scoreboard_v0.2_Haiti/pages-overlay.html?graphic=goals&backend=https%3A%2F%2Flive-cast-scoreboard-demo.onrender.com`

You can optionally add `&goal=goal-4000` to lock a browser input to one goal, instead of rotating. Add `&show=on-donation` to display it only for approximately 6 seconds when a new assigned donation triggers an alert. The global goal switch and per-goal enabled checkboxes still apply.

Put this in its own vMix Web Browser overlay at 1920×1080, keep the vMix overlay channel active with duration 0, and control visibility in the operator dashboard. The goal is positioned near the lower-left to reduce overlap with the donation alert lower-right and Top 3 upper-left. Idle graphics do not display the DEMO watermark; visible goal graphics do.

The static GitHub Pages page only renders the graphic. The Render server supplies a small public `/public/goals` feed, and keeps `/api/goals`, `/api/assign`, `/api/donations`, `/api/cast` private. No operator password or viewer token belongs in the Pages URLs.

## Do I need Google Sheets?

**No, not to use v0.5.** All settings and donations are held in local SQLite; no Sheets account or setup is required. Local Windows storage persists until you erase the database. Render Free's SQLite is ephemeral. For an actual 14-day event with paid donations, configure a durable database (e.g. managed PostgreSQL), regular backups, replay/deduplication/reconciliation with YouTube's event IDs, FX and refund rules, and operator authentication/audits. Optionally use Sheets as a ledger export and reporting destination for producers. A Sheets-only database would need careful write throttling, append-only immutable IDs and reconciliation to be safe.

## API additions (operator-only except where noted)

- `GET /api/goals` — all saved goals, visibility and calculated progress
- `POST /api/goals` — create goal
- `PUT /api/goals/{id}` — edit goal, including enabled state and baseline restart
- `DELETE /api/goals/{id}` — remove goal
- `PUT /api/goals/visibility` — global on-air switch
- `GET /api/donations?status=pending&source=youtube&q=Alice&limit=50&offset=0` — searchable private donation history
- `GET /public/goals` — public sanitized goals when `PUBLIC_OVERLAYS=1`, subject to global/per-goal visibility (all empty when hidden)

### Operator workflow checks

- Create a manually counted `Gold members` goal target 100, current 12. Enable on-air, and verify the progress bar in the goals input.
- Create automatic `4,000 PWEN` goal from now, simulate $25 with `#Marcus`, verify 25/4,000 and updated Top 3/alert.
- Add a new cast and unique tags. Simulate a Super Chat with the new tag and confirm scoring.
- Simulate `#Marcus #Avery` or no tag, search it later, assign to a selected cast and confirm no duplicate credit.
- Toggle the global goal switch OFF; all goals disappear from the goal overlay without changing cameras or vMix overlay activation.
- Export transactions as CSV before ending a demo, understanding the CSV is not a robust backup or production ledger.
