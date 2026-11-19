# Updated v0.2 note

This document was written for the earlier local-only v0.1 prototype. For current local and Render setup, follow `../README.md` and `RENDER_TEST_GUIDE.md`. The production YouTube listener and Google Sheets ledger are not connected in v0.2.

---

# Next sprint — connected rehearsal

This checklist begins **after** the offline UI and scoring simulation passes.

1. Confirm the final approved cast roster and one-word hashtag aliases; reject collisions.
2. Confirm whether broadcast output is Haitian Creole or French; have a fluent team member review all translated labels.
3. Agree on scoring policy: point multiplier, tie order, FX handling, Stickers, invalid tags, contest windows, refunds, and prize implications.
4. Create a **private** GitHub source repository. `.gitignore` excludes SQLite, OAuth tokens, and secrets.
5. Create a dedicated Google Cloud project; enable YouTube Data API v3 and Google Sheets API; configure OAuth with the show's channel owner's authorization.
6. Create a private Google Sheet with immutable donation rows, cast roster, settings, assignment/audit tabs; decide on automated backups and race-condition protection.
7. Implement a single always-on authenticated Render service with **durable** Google Sheets persistence; never rely on Render's default ephemeral filesystem for transaction data.
8. Add server-side staff login, roles and CSRF protection; the GitHub Pages frontend must not contain credentials or private donor records.
9. Implement YouTube `liveChatMessages.streamList` and resume/backoff/dedupe; handle stream switching and reconnect after deployments or network loss.
10. Add staff warning on stale listener/sheet, a fallback vMix still graphic, and a vMix rehearsal with a real controlled test purchase where feasible.
11. Rehearse 24 hours of non-stop simulated load and compare ledger totals against displayed scores before show launch.
12. Freeze deployed revision and assign overnight monitoring and on-call escalation for the 336-hour show.

Questions to production: real cast names and hashtags; number of cast members; maximum expected paid messages/minute; overlay safe-area requirements and resolution; whether the show uses one or multiple live broadcasts; whether producers can edit scores; and whether financial scoring is legally tied to prizes.
