# Live Cast Scoreboard
### A bilingual YouTube Super Chat scoreboard and vMix graphics control system

**Project type** — Live-production software, web dashboards and broadcast automation

**Stack** — Python, FastAPI, SQLite, JavaScript, HTML/CSS, GitHub Pages, Render, YouTube Data API v3, vMix

**Status:** Working demonstration through v0.5; version 1.0 production foundation developed; live-production verification still pending.

## Project overview

Live Cast Scoreboard was developed to help a reality-show production display a competitive cast ranking in response to paid YouTube interactions. Rather than requiring a graphics operator to type every donation into vMix, the system receives events, classifies them by a cast-member hashtag, applies a configurable dollar-to-points conversion, updates a scoreboard, and presents a broadcast-ready animation. The operator can intervene whenever a message lacks an unambiguous recipient.

The production graphics use a Haitian blue-and-red identity with Haitian Creole labels. The operator control room is in English so technical staff can configure goals, review events, and diagnose connections. The broadcast layout was refined using a reference clip showing a compact progress counter, timer and scrolling message rather than a conventional leaderboard.

## Problem and goals

The system needed to bridge three different tasks: **reliable donation accounting**, **fast operator corrections**, and **clean on-air presentation**. Requirements included a persistent Top 3 option, donation-triggered rankings, transparent overlays that work while switching cameras, goal progress and countdowns, multiple cast hashtags, and a defensible audit trail.

A specific challenge was traffic bursts: money must be recorded as it arrives, even when vMix cannot reasonably display each animation immediately. This led to separating the transaction ledger from the on-air playback queue.

## What we built, in sequence

**1 — Initial dashboard and scoring simulation.** We created a FastAPI backend and operator UI for simulated YouTube paid events. The scorer uses a configurable points multiplier (initially one point per USD), matches cast hashtags, prevents duplicate message IDs, and places Super Stickers or ambiguous messages into a review workflow. Real chat messages are never mistaken for paid donations.

**2 — Haitian-themed graphics for vMix.** Broadcast views use Haitian Creole text and a blue/red/white palette. A Top 3 graphic, a donation alert, and full rankings were built as transparent browser sources, allowing normal camera cuts without rebuilding the vMix input.

**3 — Deployment through GitHub and Render.** The code was pushed to GitHub. Render ran the Python API, while GitHub Pages served static overlay HTML, CSS and JavaScript. We corrected root-level asset paths, authenticated the operator dashboard, and exposed narrowly scoped public data for graphics. The browser graphics request changing scores from Render.

**4 — YouTube live and simulated sources.** A listener was added for paid Super Chat and Super Sticker events, with source labels distinguishing real YouTube purchases from simulated tests. The original demo intentionally allowed mixed-source scores, so it was treated as a demonstration rather than an official result ledger.

**5 — Goal tracking and cast management.** We added editable goals with on-air visibility switches, progress bars, optional countdowns and rotating messages. Staff can create cast entries, attach multiple hashtag aliases, and assign historical unmatched donations without duplicating the donation record.

**6 — Broadcast surge protection and production foundation.** The latest development phase adds a server-held playback queue, a dedicated operator status/links page, downloadable database backups, persistent-storage validation, and a production profile that excludes simulated donations from official rankings and on-air alerts. The combined Top 3 and alert remain synchronized.

## System architecture

```text
YouTube live paid events          Operator test events
         |                                |
         v                                v
    YouTube listener           Test event endpoint
         |                                |
         +------------+-------------------+
                      v
          Transactional event ledger
             - unique event IDs
             - cast hashtag matching
             - audit and manual review
                      |
            +---------+----------+
            |                    |
            v                    v
     Live cast scores       Broadcast queue
     Goals and ranking      Pending / playing / done
            |                    |
            +---------+----------+
                      v
            Public broadcast API
                      |
              GitHub Pages JS
                      |
          Transparent graphics in vMix
```

In the production profile, test events remain available for diagnostics, but public scores and broadcast delivery are calculated from actual YouTube paid events only.

## Operator features

- Cast roster and multiple aliases per cast member
- Super Chat and Super Sticker classification; USD points conversion
- Searchable review of unmatched donations and recorded corrections
- Multiple configurable targets, progress bars, countdowns and manual goals
- Permanent or donation-triggered Top 3 plus synchronized donation alerts
- English control room and Haitian Creole producer/broadcast views
- System status: API, database integrity, YouTube connection, event counts and queue size
- Server-side broadcast controls: pause, resume and skip without changing scores
- Stable GitHub Pages links with a central public server configuration file
- Test events and downloadable SQLite database backups

## Reliability and security design

The application stores donation identifiers uniquely so repeated API deliveries do not duplicate points. Manual assignments update the existing transaction rather than creating a new one. The on-air queue has its own state, so broadcast animation is decoupled from scoring and can recover across vMix browser reloads. Public graphics endpoints omit operator credentials and raw donation messages; control endpoints remain authenticated.

The production profile is designed for a paid single-node server with persistent storage. It rejects an obviously ephemeral database configuration rather than silently running official results from a temporary file. Test transactions are excluded from live scores in that profile.

## Technical challenges and solutions

**Relative paths and deployment.** Early deployment returned blank pages because the Python server expected HTML assets in a nonexistent `web/` directory. Asset serving and routes were aligned to the actual repository structure.

**Protected Render pages vs public graphics.** vMix could not log into restricted pages reliably. Separating the GitHub Pages presentation layer from authenticated operations gave the graphics safe read-only data access.

**Overlay behavior.** A permanent leaderboard was useful but not always desired. We added donation-triggered display modes and a combined alert/Top 3 layout to keep camera switching independent of graphics timing.

**Ambiguous donations.** A message may have no hashtag, multiple tags, or no textual content (Super Sticker). These cases require operator assignment with a recorded reason, not a guess from the software.

**Surges.** A large donation burst can produce more alerts than fit into broadcast time. The production foundation moves sequencing to the server and adds an operator queue. An optional, operator-enabled burst summary groups on-air acknowledgments without removing the underlying donation records; higher-throughput and real-stream validation remain launch work.

## Validation and current state

The v0.5 demonstration was confirmed working with Render and GitHub Pages. Automated tests cover the parser, scoring logic, authentication boundaries, goals and browser overlays. The production foundation adds source-isolation and queue tests; its live YouTube listener, paid host, recovery process and 14-day endurance have **not yet been validated as an operational production system**.

## Next milestones

A paid server and persistent data volume, off-server automated backups, an official-stream ingestion test, reconnect/reconciliation procedures, staff authentication improvements, and load/endurance testing will precede any use as an official scoring source. A future move to PostgreSQL will support multiple server instances and more advanced queue coordination.

## Deployment and handoff workflow

The working demonstration is deployed from GitHub to Render Free, with static graphics published on GitHub Pages. The production migration is deliberately a separate deployment: create a paid service with attached persistent storage, configure the operator and YouTube secrets, publish the backend hostname in one public GitHub Pages configuration file, and then validate the existing vMix graphics URLs.

The operator can open a dedicated **System & links** page to check the running version, database integrity, live YouTube connection, public graphics availability, queue status and the exact URLs to paste into vMix. It also provides an authenticated download of a consistent database backup. The control room can pause, resume or skip graphics and optionally enable burst summaries without changing the underlying donation ledger.

## Verification workflow

The automated regression suite exercises scoring, duplicates, cast matching, history search, authorization, goals, queue operations and live-versus-test source isolation. A load test inserts 500 test events twice, verifies each event is recorded only once and checks that production totals remain unaffected. A separate grouping test verifies that 30 real event records remain intact when on-air animations are summarized.

Before an actual 14-day broadcast, the remaining checks must be performed on the chosen paid server with a real livestream: event collection after reconnects, recovery from server restarts, reconciliation against YouTube's records, restore from independent backups, and validation that the show graphics remain synchronized under rapid donation bursts.

## Project links

- Source repository: https://github.com/HeathLyon/Live_Cast_Scoreboard_v0.2_Haiti
- Static graphics: https://heathlyon.github.io/Live_Cast_Scoreboard_v0.2_Haiti/pages-setup.html
- Existing demonstration backend: https://live-cast-scoreboard-demo.onrender.com/health

*Public case study: no credentials, private API keys or viewer tokens are included.*
