## DemoForge – Borderpass Demo Script (5–7 minutes)

This is a suggested live demo flow for the Borderpass “Best hack for Demos and QA” track.

### 1. Intro: problem and architecture (≈1 minute)

- Start on the **landing** or main README page (or a simple landing screen in the app).
- Say what DemoForge is:
  - “DemoForge is a control plane for **on-demand, production-parity sandboxes** with zero real data. It gives teams presets, config, capture → templates, and lifecycle controls.”
- Briefly explain the architecture:
  - Frontend (Next.js dashboard) → FastAPI orchestrator (`backend/main.py`) → Python agents (`backend/agent.py`) → Docker containers built from `sandboxes/*/` → local Ollama model.
  - Mention that everything runs on your Mac Pro (Docker, FastAPI, Ollama) and you’re controlling it from your MacBook via Tailscale.

### 2. Launch a preset with manifest-driven config (Foods + Bank) (≈2 minutes)

1. Open the **control panel** (the main dashboard) and point at the **preset cards**:
   - Favorite Foods (Flask + SQLite, synthetic foods list).
   - Bank (Flask + SQLite, synthetic bank accounts and transactions).
   - Call out that each preset has a `manifest.json` describing endpoints, synthetic data, default goal, and config knobs.
2. Click **Favorite Foods**:
   - Show the manifest summary at the top of the config panel (synthetic data + capabilities).
   - Highlight the **App title** field and explain it comes from `config_schema` in `sandboxes/preset/manifest.json`.
   - Set a fun title, e.g. “Borderpass Foods QA”, and a short goal like “Add a goofy food every 5 seconds”.
   - Set **Expires in** to 5 minutes.
   - Click **Launch sandbox**, then open the sandbox URL and show:
     - The title from config.
     - Foods being added over time by the agent (logs show real `curl` commands to `/add`).
3. Return to the dashboard and click **Bank**:
   - Show the manifest summary: accounts, transfers, health, and now `/api/seed`.
   - Point at the config controls (App title, Currency) and mention they are driven by `config_schema` in `sandboxes/bank/manifest.json`.
   - Set App title to something like “Borderpass QA Bank” and Currency to “CAD”.
   - Set goal: “Seed the database with 50 users and run a transfer demo.”
   - Launch and open the sandbox URL:
     - Show that many accounts have been created and at least one transfer appears in the transaction list.
     - Mention that the agent is issuing real shell commands, e.g. `curl -s -X POST .../api/seed ...` and `curl -s -X POST .../api/transfer ...`.

### 3. Capture and replay a walkthrough (templates as reusable scenarios) (≈2 minutes)

1. With the **Bank** sandbox still running:
   - Click **Capture** for that sandbox in the Active sandboxes table.
   - Point out that “Recording (N steps)” increments as the agent runs commands.
2. After a few seconds (enough to seed + maybe one transfer), click **Stop & save**:
   - Enter a name like “Bank seeding QA run” and Save.
   - Call out the success message and mention how many steps were recorded.
3. Scroll to the **Saved templates / replays** section:
   - Show the new template with name, preset, and steps count.
   - Explain: “This is now a **reusable QA/demo scenario** – a deterministic series of shell commands.”
4. Click **Launch replay** for that template:
   - A new sandbox appears with a **Replay** badge in the Active sandboxes table.
   - Open the new sandbox URL; show that it already has the seeded accounts and transfers.
   - Mention that in replay mode, the agent does **not** call the LLM; it just replays the recorded commands, with URLs rewritten to the **new** sandbox so it’s truly a fresh environment.

### 4. Lifecycle controls: reset, expiry, and cleanup (≈1–1.5 minutes)

1. In the Active sandboxes table:
   - Demonstrate **Reset** on one sandbox: click Reset, show that a new container starts with the same preset, config, and goal but a fresh database.
2. Show **Expires in**:
   - Launch a sandbox with **Expires in = 1 min**.
   - Point at the Expires column showing both the timestamp and “(in 1 min)”. Explain that after expiry, DemoForge cleans up sandboxes lazily on status checks.
3. Mention **Destroy**:
   - Destroy one sandbox and show it disappears from the list and its container+agent are killed.
4. Briefly mention **shareability and roles**:
   - URLs are shareable (Tailscale IP); role-based access (viewer/operator/owner) is obvious future work.

### 5. Onboarding a new app as a preset (≈1 minute)

1. Open `docs/NEW_PRESET_ONBOARDING.md` and summarize the checklist:
   - Drop any app into `sandboxes/<id>/` with a Dockerfile that listens on `0.0.0.0:8501`.
   - Have the app read env vars for config (e.g. `APP_TITLE`, feature flags).
   - Add a `manifest.json` describing endpoints, example commands, default goal, and `config_schema` for the UI.
   - Add `"my-app": "demoforge/my-app:latest"` to `PRESETS` in `backend/config.py`.
   - Run `make build-sandboxes` and the app appears as a new preset card with controls.\n+2. Explain that this makes DemoForge a **platform**: any team in the company can plug in a new service and get:\n+   - On-demand sandboxes.\n+   - Manifest-driven config UI.\n+   - Capture → templates for reusable demos and QA scenarios.\n+\n+### 6. Wrap-up talking points\n+\n+- Manifest-driven presets provide a clear contract for each sandbox (endpoints, defaults, config knobs).\n+- Agents read those manifests and issue real shell commands (curl and loops) to control apps.\n+- Capture and templates give a lightweight way to turn runs into reusable, deterministic scenarios.\n+- Lifecycle controls (launch, reset, expiry, destroy) and `make build-sandboxes` give reliability and operability during demos.\n+\n*** End Patch***"}]}}]><![CDATA[]]></commentary>
