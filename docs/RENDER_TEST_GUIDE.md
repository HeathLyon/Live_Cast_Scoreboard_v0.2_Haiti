# Render sandbox testing — Live Cast v0.5 Haiti

For YouTube setup and synchronized donation graphics, see [YouTube live demo](YOUTUBE_LIVE_DEMO.md). Render Free uses temporary SQLite. Records may disappear after restarts or redeployments, and the graphics display a DEMO watermark.

## Preflight

1. First run the app locally and pass the simulated donation checklist in `README.md`.
2. Have a GitHub account and a Render account. **Do not commit your Render passwords to GitHub.**
3. Use a **private GitHub repository** if you're sharing internal production source. HTML/CSS assets are public once hosted, but API and interfaces are protected using the setup below.
4. Generate **two different secrets** on your local machine:

   ```powershell
   py -c "import secrets; print(secrets.token_urlsafe(32))"
   py -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

   Use the first as `OPERATOR_PASSWORD` and second as `VIEW_TOKEN`. They are independent. Store securely. They must not be added to the repository.

## Deploy

1. Push the **contents of this project folder** to GitHub. Keep `app.py`, `index.html`, `producer.html`, `overlay.html`, `css/`, `js/`, and `render.yaml` at repository root. **Do not** create a `web/` folder. Do not upload `.venv`, `*.sqlite3`, `.env`, or secrets. Use `.gitignore`.
2. At [Render](https://dashboard.render.com/), select **New → Blueprint**. Connect the repository containing `render.yaml`. Review the planned resources: **one Free web service**, no database.
3. When prompted for environment variables, paste `OPERATOR_PASSWORD` (12+ characters) and `VIEW_TOKEN` (24+ characters). The `render.yaml` contains **only variable names** for these secrets, not their values.
4. Deploy. Render will run `pip install -r requirements.txt`, then start `uvicorn app:app --host 0.0.0.0 --port $PORT --workers 1`.
5. Open `https://YOUR-RENDER-HOST.onrender.com/health` and expect `"ok":true` and `"mode":"simulation"`.
6. Visit `https://YOUR-RENDER-HOST.onrender.com/`. Your browser should ask for credentials. Enter username `operator` and the `OPERATOR_PASSWORD` value.
7. Use the Donation Simulator to add `#Marcus` with `$25.00`; reload and verify points. Open the Top 3 overlay with your logged-in operator browser.
8. To share **read-only** views with a producer or the vMix browser input, append your `VIEW_TOKEN` in the URL:

   - Producer display: `https://YOUR-RENDER-HOST.onrender.com/producers?view_token=YOUR_VIEW_TOKEN`
   - Top 3 + donation alert: `https://YOUR-RENDER-HOST.onrender.com/overlay/top3-alert?view_token=YOUR_VIEW_TOKEN`
   - Goals: `https://YOUR-RENDER-HOST.onrender.com/overlay/goals?view_token=YOUR_VIEW_TOKEN`
   - Persistent Top 3: `https://YOUR-RENDER-HOST.onrender.com/overlay/top3?view_token=YOUR_VIEW_TOKEN`
   - Alert: `https://YOUR-RENDER-HOST.onrender.com/overlay/alert?view_token=YOUR_VIEW_TOKEN`
   - Full: `https://YOUR-RENDER-HOST.onrender.com/overlay/full?view_token=YOUR_VIEW_TOKEN`

   Treat the viewer token as a secret. Anyone with it can view the demo scoreboard. Do not publish these links on social media or a public GitHub Pages site. To revoke, rotate `VIEW_TOKEN` in Render's Environment settings and redeploy.

## Cost and operational cautions

- `render.yaml` defaults to the **Free** plan for testing. Free web services sleep after 15 minutes without inbound traffic and can take around a minute to wake; they also restart periodically. They are **not** suitable for a 24/7 live listener. Upgrade to a paid always-on service for production.
- Only **one Uvicorn worker** and **one instance** are intended for this SQLite demo.
- **Do not use for real competition scoring.** The Render demo uses temporary SQLite and supports USD scoring. YouTube listening requires a server-side API key.
- `autoDeploy: false` prevents routine Git pushes from interrupting your running test. Trigger a manual deploy when you intend to update.
- Current demo uses HTTP Basic for operator login. A future production release should replace this with individual user accounts, HTTPS cookie sessions, roles, audit logging, and rate limiting.
- vMix and remote viewers connect directly to the Render-hosted browser pages for this test. GitHub Pages is **not required** to run this build remotely.

## Local alternative

The same source runs on Windows with `setup_windows.bat` then `start_windows.bat`; local mode binds to `127.0.0.1:8000` and does **not** prompt for a password. Never run local mode publicly on a network interface.

## Root paths for remote graphics

- The Python app serves root HTML files directly. For nested `/overlay/top3` URLs, the browser resolves relative assets under `/overlay/css/` and `/overlay/js/`; the app explicitly serves those routes too.
- CSS and JS are safe public assets. The API still requires an operator login or a read-only `VIEW_TOKEN` on approved GET routes.
- If an existing paid Render service has already been created, editing `render.yaml` alone may not change its billing plan immediately. Check **Service → Settings → Instance Type** and switch to Free before confirming the deployment.

## v0.5: Goals & searchable donation review

After uploading the v0.5 code, deploy latest commit. Render `/health` will report `0.5.0`. In the English operator dashboard, open **Goals & ticker**. Creating a goal does not immediately put it on air: the global **Show goals ON AIR** switch initially defaults to OFF; enable it after you have set up a safe test goal. You can also enable/disable individual goals. The public `/public/goals` endpoint returns only broadcast-safe active goals while this switch is ON (requires `PUBLIC_OVERLAYS=1`).

Open `https://heathlyon.github.io/Live_Cast_Scoreboard_v0.2_Haiti/pages-setup.html` to generate the new `graphic=goals` link for vMix. Use **Synchronized Top 3 and donation alert** for both donation-triggered cards in one vMix input. Put Goals in its own overlay input.

For older ambiguous Super Chats use **Assignment queue → Search donation history**. Choose pending, search by donor, comment or event ID and assign with a written reason. All transactions in the demo remain temporary on Render Free; downloaded CSV is a manual snapshot, not a persistent backup. For production, select a managed durable database and backups before enabling real scoring.
