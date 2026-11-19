# Render sandbox testing — Live Cast v0.2 Haiti

**Simulation only:** This configuration contains **no real YouTube API connection and no Google Sheets integration.** Test records on Render's default filesystem are **ephemeral** and may vanish after restarts, redeployments, or infrastructure replacement. The app deliberately displays DEMO watermarks on all graphics.

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

1. Push the **contents of this project folder** (with `app.py` and `render.yaml` at repository root) to GitHub. Do not upload `.venv`, `*.sqlite3`, `.env`, or secrets. Use `.gitignore`.
2. At [Render](https://dashboard.render.com/), select **New → Blueprint**. Connect the repository containing `render.yaml`. Review the planned resources: **one Free web service**, no database.
3. When prompted for environment variables, paste `OPERATOR_PASSWORD` (12+ characters) and `VIEW_TOKEN` (24+ characters). The `render.yaml` contains **only variable names** for these secrets, not their values.
4. Deploy. Render will run `pip install -r requirements.txt`, then start `uvicorn app:app --host 0.0.0.0 --port $PORT --workers 1`.
5. Open `https://YOUR-RENDER-HOST.onrender.com/health` and expect `"ok":true` and `"mode":"simulation"`.
6. Visit `https://YOUR-RENDER-HOST.onrender.com/`. Your browser should ask for credentials. Enter username `operator` and the `OPERATOR_PASSWORD` value.
7. Use the Donation Simulator to add `#Marcus` with `$25.00`; reload and verify points. Open the Top 3 overlay with your logged-in operator browser.
8. To share **read-only** views with a producer or the vMix browser input, append your `VIEW_TOKEN` in the URL:

   - Producer display: `https://YOUR-RENDER-HOST.onrender.com/producers?view_token=YOUR_VIEW_TOKEN`
   - Top 3: `https://YOUR-RENDER-HOST.onrender.com/overlay/top3?view_token=YOUR_VIEW_TOKEN`
   - Alert: `https://YOUR-RENDER-HOST.onrender.com/overlay/alert?view_token=YOUR_VIEW_TOKEN`
   - Full: `https://YOUR-RENDER-HOST.onrender.com/overlay/full?view_token=YOUR_VIEW_TOKEN`

   Treat the viewer token as a secret. Anyone with it can view the demo scoreboard. Do not publish these links on social media or a public GitHub Pages site. To revoke, rotate `VIEW_TOKEN` in Render's Environment settings and redeploy.

## Cost and operational cautions

- `render.yaml` defaults to the **paid Starter** plan to avoid idle spinning down. Confirm the current price and any usage fees when creating the service. You can manually select Free for casual demonstration, but Free web services sleep after idle, so they are **not** appropriate for a 24/7 production.
- Only **one Uvicorn worker** and **one instance** are intended for this SQLite demo.
- **Do not use for real competition scoring.** The Render demo has no Google Sheets storage, no automatic YouTube listener, no FX conversion, and no production-grade backups.
- `autoDeploy: false` prevents routine Git pushes from interrupting your running test. Trigger a manual deploy when you intend to update.
- Current demo uses HTTP Basic for operator login. A future production release should replace this with individual user accounts, HTTPS cookie sessions, roles, audit logging, and rate limiting.
- vMix and remote viewers connect directly to the Render-hosted browser pages for this test. GitHub Pages is **not required** to run this build remotely.

## Local alternative

The same source runs on Windows with `setup_windows.bat` then `start_windows.bat`; local mode binds to `127.0.0.1:8000` and does **not** prompt for a password. Never run local mode publicly on a network interface.
