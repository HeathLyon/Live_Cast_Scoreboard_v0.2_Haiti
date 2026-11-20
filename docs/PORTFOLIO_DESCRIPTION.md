# Live Cast Scoreboard — Project description

I developed a bilingual live-production scoreboard that turns YouTube Super Chats into a cast-member ranking and animated broadcast graphics. Built with Python/FastAPI and a lightweight HTML/CSS/JavaScript frontend, it connects a protected operator dashboard to transparent vMix browser overlays through GitHub Pages.

The system matches paid messages to cast members using configurable hashtags, scores USD donations, prevents duplicate event counting, and routes ambiguous or untagged Super Chats to an operator for review. Producers can add contestants and hashtag aliases, create countdowns and progress goals, and show the Top 3 standings together with an animated donation alert—all while the director continues switching cameras normally.

During development, I deployed the dashboard on Render, separated browser graphics from the backend, refined the Haitian Creole broadcast layouts from a reference show clip, and built a working demonstration with test donations. The next engineering phase introduced a server-managed alert queue, real-versus-test score isolation, connection diagnostics, stable graphic URLs and a paid-server migration path.

**Technology:** Python, FastAPI, SQLite, YouTube Data API v3, JavaScript, HTML/CSS, GitHub Pages, Render and vMix. **Current status:** Working demo; production infrastructure and endurance testing in progress.

**Repository:** https://github.com/HeathLyon/Live_Cast_Scoreboard_v0.2_Haiti
