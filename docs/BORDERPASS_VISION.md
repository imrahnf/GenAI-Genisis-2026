# DemoForge × Borderpass: Vision to Win

**Track:** *Create a platform for on-demand sandbox environments with production-parity behavior and zero real data. Teams can define reusable demo or QA scenarios that control sandbox contents and enabled features, with a lightweight way to capture walkthroughs and turn them into reusable templates. Each scenario launch produces a fresh, shareable sandbox with synthetic data, role-based access, and lifecycle controls like reset and expiry—all managed through a control panel or API.*

---

## 1. Map: Track Wording → Our Product

| Track requirement | What we build | Status / plan |
|------------------|----------------|----------------|
| **On-demand sandbox environments** | Launch → get URL in seconds; no long-lived shared env | ✅ Done |
| **Production-parity behavior** | Real app in container (same stack as prod); no mocks | ✅ Done (preset is real Flask/SQLite) |
| **Zero real data** | Synthetic only (foods, seed data); no PII, no prod DB | ✅ Done |
| **Teams define reusable demo or QA scenarios** | **Scenarios** = named bundle (image + config + agent settings + optional template) | 🔲 Build |
| **Control sandbox contents and enabled features** | **Config** per scenario: synthetic data opts, feature flags, env vars | 🔲 Build |
| **Lightweight capture of walkthroughs → reusable templates** | **Capture**: record agent commands (and optional annotations) during a run; save as **Template**. **Replay** or **guide** new runs from template | 🔲 Build (killer feature) |
| **Fresh, shareable sandbox** | Each launch = new container; shareable Tailscale/public URL | ✅ Done |
| **Synthetic data** | Per-scenario seed data / data shape; agent or script populates | ✅ Partial (agent adds data); extend with “seed” config |
| **Role-based access** | **Roles** per sandbox or per scenario: Viewer (see only), Operator (trigger agent, reset), Owner (destroy, edit) | 🔲 Build |
| **Lifecycle: reset and expiry** | **Reset** = new container from same scenario, same or new URL. **Expiry** = TTL (e.g. 2h) then auto-destroy | 🔲 Build |
| **Control panel or API** | Dashboard + REST API for launch, destroy, status, scenarios, templates | ✅ API + UI; extend for scenarios/templates |

---

## 2. The “Prompt Thing” and Beyond: Scenarios + Config + Templates

Right now: **one goal string** per launch. To win, we turn that into a **scenario** with rich config and optional **walkthrough templates**.

### 2.1 Scenarios (reusable demo or QA scenarios)

A **scenario** is a named, reusable definition that teams can share and launch repeatedly.

- **Name** (e.g. “Bank fraud demo”, “Food app QA”).
- **Source**
  - **Preset**: one of N built-in presets (each = known Docker image, e.g. `demoforge/preset`, `demoforge/bank`).
  - **Custom image**: any image from a registry (e.g. `myregistry.azurecr.io/demo-bank:latest`). Validated at launch (pull and run).
- **Config** (controls “sandbox contents and enabled features”):
  - **Synthetic data**: e.g. “load 50 customers”, “industry: banking”, “seed: high_fraud”. Passed as env or to a seed script/agent.
  - **Feature flags / env**: key-value env vars for the container (e.g. `FEATURE_FRAUD_DETECTION=true`).
  - **Agent settings**:
    - **System prompt / goal**: the “agent prompt” (current goal, but richer: e.g. “You are a QA bot. Add foods every 5s with goofy names.”).
    - **Model** (optional override): e.g. `phi3:mini`, `llama3.2`.
    - **Interval, timeout, max steps** (optional).
    - **Allowed tools** (optional): e.g. “only curl to this host” for safety narrative.
- **Optional: Walkthrough template** (see below). If set, each launch can “replay” or “follow” that template.

Stored as: JSON or DB row; editable in control panel and via API. Launch = “launch scenario X” with optional overrides.

### 2.2 Walkthrough capture → reusable templates (lightweight)

This is the **differentiator** for the track.

- **Capture**
  - User starts a sandbox (from a scenario).
  - User clicks **“Start capture”** in the control panel (or API). From that moment, the backend records:
    - Every **agent command** (the exact curl/shell) and its **output** (stdout/stderr, truncated).
    - Optional: **annotations** (user adds a short “step name” or “this is the fraud trigger”).
  - User clicks **“Stop capture”** and **“Save as template”** → name it (e.g. “Bank fraud walkthrough”). Stored as an ordered list of steps: `[{command, output, annotation?}, ...]`.

- **Template**
  - A **template** = saved walkthrough (list of steps). It’s attached to a scenario (or generic) and can be reused.

- **Reuse**
  - **Option A – Replay (deterministic):** When launching a sandbox with a template, the agent **replays** the recorded commands in order (with optional delay). No LLM for replay; just run step 1, step 2, … So “same demo every time.”
  - **Option B – Guided (LLM + template):** The template is passed to the LLM as context: “Follow this sequence of actions. Step 1: … Step 2: … Adapt if the app state differs.” Agent still uses LLM but is guided by the template. Better for QA where you want variation but same structure.

For “lightweight”: capture is **one button**, save is **name + optional annotations**. No video, no DOM recording—just agent commands. That’s enough to show “capture walkthroughs and turn them into reusable templates.”

### 2.3 Control panel: presets vs custom image

- **Presets**: dropdown of N presets (e.g. “Favorite foods”, “Bank demo”). Each preset has a default scenario (default config + default agent prompt). User can override config and agent settings before launch.
- **Custom image**: text input for image name (e.g. `registry.io/my-demo:v1`). On launch, backend pulls and runs it. Scenario can still have default config and agent prompt; user can override.

So: **one of N presets OR pull from registry**, with **rich config and agent settings** (not just one goal string).

### 2.4 Roles (role-based access)

- **Viewer**: can see sandbox URL and logs; cannot trigger agent, reset, or destroy.
- **Operator**: can trigger “run agent step”, reset, view logs; cannot destroy or edit scenario.
- **Owner**: full control (destroy, edit scenario, delete template).

Implementation: per sandbox (or per “team link”) we store a role. Control panel grays out or hides actions by role. API returns 403 for disallowed actions. For hackathon, even a simple two-role model (Viewer vs Owner) plus “share as view-only link” would tick the box.

### 2.5 Lifecycle: reset and expiry

- **Reset**: Button “Reset” = destroy current container (and agent), create a **new** container from the **same scenario** (same config, same image). Option: keep same URL (if you use a reverse proxy that maps path to container) or assign new URL. Result: “fresh sandbox, same scenario.”
- **Expiry**: When launching, user (or scenario default) sets **expires_in** (e.g. 2 hours). Backend stores expiry time; a small cron or periodic task (or check on next status call) destroys sandboxes past expiry. Control panel shows “Expires at 14:30”.

---

## 3. Data model (minimal)

- **Scenario**: `id, name, source_type (preset | custom_image), image (preset key or image name), config (JSON), agent_settings (JSON), template_id?`.
- **Template**: `id, name, scenario_id?, steps: [{command, output, annotation?}]`.
- **Sandbox** (runtime): `id, scenario_id?, template_id?, url, port, expiry_at?, role (viewer | operator | owner), created_at`.
- **Capture** (runtime): while capturing, append to a buffer; on “Save as template”, create **Template** and optionally attach to **Scenario**.

---

## 4. API sketch (control panel + API)

- `GET/POST /scenarios` – list, create.
- `GET/PUT/DELETE /scenarios/:id` – get, update, delete.
- `POST /launch` – body: `scenario_id` (or preset name + overrides) or `image` (custom) + optional `config` override + optional `template_id` + optional `expires_in` + optional `role`. Returns `sandbox_id`, `url`, etc.
- `POST /sandboxes/:id/reset` – reset sandbox (new container, same scenario).
- `POST /sandboxes/:id/capture/start` – start recording agent commands.
- `POST /sandboxes/:id/capture/stop` – stop; optional body `save_as_template: true, name: "..."`.
- `GET /templates` – list templates (optionally by scenario).
- `GET/POST /sandboxes/:id/destroy` – destroy (existing).
- `GET /status` – list sandboxes with expiry, role, scenario name.

---

## 5. What to build first (order)

1. **Scenarios (backend + UI)**  
   Preset vs custom image; name; config (env, synthetic data flags); agent_settings (system prompt, model, interval). Launch by `scenario_id` or by preset name + overrides. No template yet.

2. **Expiry**  
   Store `expires_in` on launch; store `expiry_at` on sandbox; background or lazy cleanup. Show in UI.

3. **Reset**  
   “Reset” = destroy container + agent, then launch same scenario again (new container). New URL unless you add a proxy.

4. **Capture + templates**  
   Record agent commands (and optionally outputs) during a run; “Save as template”; store steps. **Replay** mode: when launching with a template, agent runs recorded commands in order (no LLM). This is the “lightweight way to capture walkthroughs and turn them into reusable templates.”

5. **Guided mode (optional)**  
   When launching with a template, option “guided”: pass template steps to LLM as context so it “follows” the sequence. Adds variety while staying on script.

6. **Roles**  
   Per-sandbox role (viewer / operator / owner); enforce in API and UI (hide/disable actions).

7. **Polish**  
   Control panel: scenario dropdown, config form, template dropdown, “Capture” button, “Reset”, “Expires at”, role badge. Docs and one diagram for “production-parity + zero real data + lifecycle.”

---

## 6. “Most fucking cool” summary

- **One place** to pick **preset or any registry image**, set **config + agent settings**, and optionally **attach a captured walkthrough** so every launch is the same demo or the same QA script.
- **One button** to **capture** a run (agent commands) and **save as template**; next launch can **replay** that template so “the demo runs itself.”
- **Lifecycle**: reset (fresh container, same scenario) and expiry (auto-cleanup).
- **Roles**: share a link as view-only or operator so “teams” and “role-based access” are real.
- **Control panel + API**: everything doable from the UI and from the API so it’s a platform, not a one-off tool.

That’s how the “prompt thing” becomes **scenarios with config, agent settings, and reusable walkthrough templates**—and how DemoForge directly hits every line of the Borderpass track.
