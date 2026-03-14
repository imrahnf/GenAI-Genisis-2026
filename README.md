# DemoForge

Ephemeral demo sandboxes: one preset (favorite foods app), one shared LLM (Ollama), per-sandbox agents. Run everything on the Mac Pro; open the dashboard from your MacBook at `http://<mac-pro-tailscale-ip>:3000`.

**→ [Brief analysis](docs/BRIEF_ANALYSIS.md)** — how the codebase maps to the hackathon brief; gaps and final-setting notes.

**→ [Use guide](docs/USE_GUIDE.md)** — Config, Expires, Capture, Templates and how to test.

---

## How to run (full setup)

Do these once, in order. After that, “Launch sandbox” starts a container from the image you built—**no rebuild each time**.

### 1. Docker (required)

You need a Docker daemon so the backend can run sandbox containers.

**Option A — Docker Desktop**  
Start Docker Desktop and wait until it’s running.

**Option B — Colima (CLI only, no Desktop)**  
If you can’t use Docker Desktop (e.g. headless / SSH):

```bash
brew install colima docker
colima start
docker info   # verify
```

Later: `colima stop` / `colima start` to stop or start the daemon.

---

### 2. Build preset images (once)

All sandbox code lives under **`sandboxes/`**. Build each preset image once (no registry pull at runtime):

```bash
# Build all sandboxes in one go
make build-sandboxes

# or build individual presets explicitly
docker build -t demoforge/preset:latest sandboxes/preset/
docker build -t demoforge/bank:latest sandboxes/bank/
```

- **preset** — Favorite foods app (Flask + SQLite, `POST /add`).
- **bank** — Mini banking app (accounts, transfers; `POST /api/accounts`, `POST /api/transfer`, `POST /api/seed`).

Each “Launch sandbox” runs a container from the chosen preset image. Rebuild only when you change that preset’s code.

---

### 3. Ollama (optional, for the agent)

The agent can add foods / drive the apps via the LLM or a **fallback list**. To use the LLM on the Mac Pro:

```bash
ollama serve

# Recommended default model (good quality, still CPU-friendly)
ollama pull llama3.1:8b

# Fallback (smaller) model also supported
ollama pull phi3:mini
```

Then, before starting the backend, pick a model for DemoForge by setting `OLLAMA_MODEL`:

```bash
export OLLAMA_MODEL=llama3.1:8b   # recommended
# or
export OLLAMA_MODEL=phi3:mini     # smaller/faster fallback
```

`backend/agent.py` reads `OLLAMA_MODEL` at startup; all agents share that model. For plan-driven behavior (init once + continuous transfer loop), use e.g. `export OLLAMA_MODEL=qwen2.5-coder:7b`. Set `DEMOFORGE_AGENT_MAX_TOKENS=256` to cap LLM output for faster CPU inference; when the planner succeeds, the continuous phase uses a plan-driven loop (no per-step LLM). To use a remote LLM (e.g. Hugging Face Inference Endpoints), set `OPENAI_COMPATIBLE_BASE`, `OPENAI_COMPATIBLE_MODEL`, and optionally `OPENAI_COMPATIBLE_API_KEY`; see [docs/USE_GUIDE.md](docs/USE_GUIDE.md).

If the model isn’t found (e.g. you see `model '...'' not found` in the logs), the agent **still drives the apps** by running a fallback `curl` `curl` (e.g. to `/add` with a rotating list Pizza/Sushi/Sigma/etc.). This means the demo continues to work even if Ollama is misconfigured.

---

### 4. Backend (orchestrator + agents)

In a terminal, from the project root:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

If port 8000 is in use, use another (e.g. `--port 8001`). If you use a different port, set `ORCHESTRATOR_URL` so the agent can send logs: `export ORCHESTRATOR_URL=http://127.0.0.1:8001`. Leave the backend running.

---

### 5. Frontend (dashboard)

In a **second** terminal, from the project root:

```bash
cd frontend
npm install
npm run dev
```

- Dashboard: **http://localhost:3000** (or **http://\<mac-pro-tailscale-ip\>:3000** from another machine).
- If the backend is on a different port (e.g. 8001), create `frontend/.env.local` with:
  ```bash
  NEXT_PUBLIC_API_URL=http://127.0.0.1:8001
  ```
  Then restart `npm run dev`.

---

## Flow

1. Open the dashboard → choose a **Preset** (Favorite Foods or Bank), enter **Agent goal**, adjust **Config** via the preset’s controls (manifest-driven), set **Expires in** → **Launch sandbox**.
2. Backend starts a container from the preset image and an agent; you get a sandbox URL. Optionally the agent runs in **replay** mode from a saved template (no LLM) when launched from the **Saved templates / replays** section.
3. **Capture**: Start capture → let the agent run → Stop & save as template. Next launch can use that template to replay the same commands deterministically.
4. **Reset** = new container from same preset/config. **Destroy** stops the container and the agent. **Expiry** (if set) auto-destroys the sandbox.

---

## Build once, run many

- **Images** are built from `sandboxes/<preset>/`. The orchestrator only runs these pre-built images (no registry pull).
- **Containers**: each launch runs `docker run` from the selected preset image. Containers are ephemeral.

---

## Layout

- **backend/** — FastAPI: `/launch` (preset, goal, config, expires_in, template_id), `/destroy`, `/status`, `/reset`, `/capture/start`, `/capture/stop`, `/templates`, `/context/{preset}`, `/presets`. Agent script with optional **replay mode** (template).
- **sandboxes/preset/** — Favorite foods app. **sandboxes/bank/** — Mini banking app (accounts, transfers, seeding).
- **frontend/** — Preset grid + manifest-driven config panel (goal, config controls, expiry), Saved templates / replays section, sandbox table with Logs, Capture, Reset, Destroy.

---

## Agent (`backend/agent.py`)

The agent is **in the repo** at `backend/agent.py`. One process is spawned per sandbox when you click Launch.

- **Runs on the host** (same machine as the backend), not inside the container.
- **Input:** env vars from the orchestrator: `DEMOFORGE_SANDBOX_ID`, `DEMOFORGE_PORT`, `DEMOFORGE_GOAL`.
- **Behavior:** The agent **executes real shell commands** chosen by the LLM. It does **not** hardcode API calls. Each round:
  1. The LLM is given the goal and the sandbox base URL (`http://127.0.0.1:{port}`).
  2. The LLM replies with **one line**: a shell command (e.g. `curl -X POST http://127.0.0.1:8501/add -d '{"food":"Pizza"}'`) or `DONE`.
  3. The agent **runs that command** (e.g. via `subprocess`), captures stdout/stderr, and sends it back to the LLM.
  4. The LLM sends the next command or DONE. This repeats until DONE or a step limit; then the agent sleeps and starts a new round.
- So the prompt you enter (e.g. “Add a new food every 10 seconds”) drives what **commands** the LLM suggests; the agent simply executes them (e.g. `curl` to hit the sandbox). No hardcoded `/add` or other endpoints.

---

## Env (backend)

- `OLLAMA_HOST`, `OLLAMA_MODEL` — Ollama URL and model (default `phi3:mini`).
- `TAILSCALE_IP` — Override if `tailscale ip -4` isn’t available.
- Presets are defined in `backend/config.py` (`PRESETS`); images must be built from `sandboxes/<key>/`.
