# DemoForge – On‑Demand AI Sandboxes

GenAI Genesis 2026 submission

---

## What it does

DemoForge is a control panel for spinning up **ephemeral, synthetic‑data sandboxes** powered by AI agents.

- **Presets**
  - **Favorite Foods** – Flask + SQLite app; agent can add foods via API.
  - **Bank** – mini banking demo with synthetic accounts and transfers.
  - **Spending & Anomaly Tracker** – spending app where high‑value transactions are flagged as anomalies (uses `anomaly.png` as the preset thumbnail).
- **Lifecycle controls**
  - Launch, reset, and destroy sandboxes.
  - Configure expiry (no expiry / 1 min / 5 min / 1–2 h).
- **Agent capture & replay**
  - Start **Capture** on a sandbox while you click through it.
  - Stop and save as a **Template**.
  - Re‑launch that walkthrough on a fresh sandbox from **Replays**.
- **Live visibility**
  - **Sandboxes** table with status, logs, and actions per sandbox.
  - **Lifecycle** graph that shows launches, recordings, replays, and destroyed sandboxes.
  - Agent logs with timestamps and colored types (info / LLM / error).

All sandboxes use **synthetic data only** – safe for demos and QA.

---

## What it uses

### Frontend

- **Next.js 14** (App Router) + **React 18**
- **Tailwind CSS** with a custom dark theme (flat `#1a1a1a`, green accent)
- **Geist Sans / Geist Mono** fonts for a modern developer aesthetic
- **Framer Motion** for animated toasts and micro‑interactions
- **ReactFlow + dagre** for the lifecycle graph
- **lucide-react** icons

The frontend is a single page (App Router) that talks to the backend via `fetch`, orchestrating all state and passing it into presentational components like `PresetsSection`, `LaunchSandboxForm`, `SandboxesSection`, `ReplaysSection`, and `LifecycleSection`.

**Agents** are Python subprocesses that:

- Read goals and config from environment variables.
- Interact with the sandbox app over HTTP.
- Stream logs back to `/agent-log`.

---

## How to run locally

### 1. Backend (FastAPI + agents)

From the project root:

```bash
cd backend

# Create and activate a virtual environment (optional but recommended)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the backend orchestrator
uvicorn main:app --host 0.0.0.0 --port 8001
```

The backend will expose the JSON API at `http://127.0.0.1:8001`.

### 2. Frontend (Next.js dashboard)

In a second terminal:

```bash
cd frontend
npm install

# Configure environment for local dev
cat > .env.local << 'ENV'
NEXT_PUBLIC_API_URL=http://127.0.0.1:8001
NEXT_PUBLIC_APP_URL=http://localhost:3000
ENV

# Start the dev server
npm run dev
```

Open **[http://localhost:3000](http://localhost:3000)** in your browser.

