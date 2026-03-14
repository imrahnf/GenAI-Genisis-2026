# DemoForge – Use guide and concepts

This guide explains **Config**, **Expires in**, **Capture**, **Templates**, and **Scenarios**, and gives you a step-by-step way to test everything.

---

## 1. Concepts (what each thing is for)

### Config (JSON env overrides)

- **What it is:** Optional JSON object of environment variables passed into the **container** when it starts.
- **Why:** Presets (e.g. Favorite Foods, Bank) can read env vars to change behavior (title, feature flags, etc.) without rebuilding the image.
- **Example:** `{"APP_TITLE":"My Demo"}` — if the app reads `APP_TITLE`, it will see "My Demo". Leave `{}` or empty if you don’t need overrides.
- **Scope:** Per launch. Not stored in scenarios/templates unless you copy it into a scenario.

---

### Expires in

- **What it is:** How long the sandbox is allowed to live. After that time, the orchestrator treats it as expired and will destroy it (lazy cleanup when you call **Status** or other endpoints).
- **Why:** Demos/QA often need short-lived environments so they don’t stick around forever.
- **How it shows:** When you set e.g. “5 min”, the **Expires** column in “Active sandboxes” shows the expiry time and a countdown like “2:30 PM (in 5 min)”. If you leave “No expiry”, the column shows “—”.
- **Important:** You must **choose an expiry** (e.g. “5 min”) in the launch form for the Expires column to show a value. If you leave “No expiry”, the column correctly shows “—”.

---

### Capture (walkthrough recording)

- **What it is:** While a sandbox is running, you can **start capture**. From that moment, every **command** the agent runs (and its **output**) is recorded. When you **stop & save**, that sequence is stored as a **template**.
- **Why:** So you can **replay** the same steps later without the LLM: launch a new sandbox with that template and the agent will run the recorded commands in order (deterministic demo/QA).
- **Flow:**
  1. Launch a sandbox (e.g. Favorite Foods, goal “Add a food every 10 seconds”).
  2. Click **Start capture** for that sandbox.
  3. Let the agent run for a bit (you should see “Recording (N steps)” increase as it runs commands).
  4. Click **Stop & save**, enter a template name, then **Save**. You’ll see a message like “Recorded N step(s). Template saved.”
- **If you see “No commands were recorded”:** Capture only stores steps when the **agent actually runs commands** and sends logs to the orchestrator. Ensure the agent is running (Ollama available, goal that causes it to run curl/commands) and that the backend can receive agent logs (same machine or correct `ORCHESTRATOR_URL`). Wait 10–30 seconds with capture on before stopping.

---

### Templates (saved walkthroughs / replay)

- **What it is:** A saved list of **command + output** steps from a capture. When you launch a sandbox and select a **Template**, the agent runs in **replay mode**: it runs those commands in order and does **not** call the LLM.
- **Why:** Deterministic demos: same steps every time. Useful for QA or showing a fixed flow.
- **How to create:** Use **Capture** (above): Start capture → let the agent run → Stop & save with a name.
- **How to use:** In the launch form, choose a template in **Template (replay)**. The new sandbox’s agent will execute that template’s steps.

---

### Scenarios (preset + default goal/config)

- **What it is:** A named bundle of: **preset**, **default goal**, and optionally default config (and later, a default template). When you **select a scenario**, the next launch uses that preset and goal (and config/template if defined).
- **Why:** Reusable “demo definitions”: e.g. “Favorite Foods – add 5 foods”, “Bank – transfer between accounts”.
- **How to create:** In the **Scenarios** section, enter a name, choose a preset, set a default goal, then **Create scenario**. The new scenario appears in the list below.
- **How to use:** In the **same Scenarios section**, use the dropdown **“Use a scenario when launching”** and select your scenario (e.g. “My Food Demo (preset)”). Then go back to the top and click **Launch sandbox**. Do **not** use the **Preset** dropdown for scenarios—Preset is only “Favorite Foods” or “Bank”; scenarios are selected in the Scenarios section.

---

## 2. Quick checks (fixes and behaviour)

### Expires column shows “—” for my sandbox

- You must select an expiry (e.g. “5 min”) **when launching**. The Expires column shows the value stored for that sandbox. If you launched with “No expiry”, it correctly shows “—”.
- After changing the UI, do a **hard refresh** and launch again with “5 min” selected; the new sandbox should show e.g. “2:30 PM (in 5 min)”.

### Capture doesn’t seem to record anything

- Capture only records when the **agent runs commands** and sends **command** and **output** logs to the orchestrator.
- Make sure:
  1. The agent is running (sandbox launched, no errors in logs).
  2. Ollama is up and the model is available (or the agent will use fallback curl and still send logs).
  3. The backend can reach the agent’s log callback: if the agent runs on the same host as the backend, leave `ORCHESTRATOR_URL` default; otherwise set it so the agent can POST to `/agent-log`.
- Wait at least 10–20 seconds with **Start capture** on, then **Stop & save**. You should see “Recording (N steps)” increase; when you save, the message will say how many steps were recorded.

### I don’t see my template after saving

- After **Stop & save**, the template list is refetched. If you don’t see it, check the success message: “No commands were recorded” means 0 steps were saved (see above). If the message says “Recorded N step(s). Template saved.”, refresh the page or re-open the Template dropdown.

---

## 3. Step-by-step test (end-to-end)

Do this once to verify Config, Expiry, Capture, Templates, and Scenarios.

### Prerequisites

- Backend and frontend running.
- Docker (or Colima) running; preset images built.
- Ollama running (optional for replay; needed for LLM-driven capture).

### A. Expires in and Expires column

1. In the launch form, set **Expires in** to **5 min**.
2. Set **Preset** to **Favorite Foods**, **Agent goal** to “Add a food every 10 seconds.”
3. Click **Launch sandbox**.
4. In **Active sandboxes**, find the new row. The **Expires** column should show a time and “(in 5 min)” (or similar). If you had left “No expiry”, it would show “—”.

### B. Config (optional)

1. If your preset app supports an env var (e.g. `APP_TITLE`), set **Config** to e.g. `{"APP_TITLE":"My Demo"}` and launch. Otherwise leave `{}` and skip.

### C. Capture and template

1. Launch a sandbox (e.g. Favorite Foods, goal “Add a new food every 10 seconds”), **Expires in** = No expiry or 5 min.
2. Wait until the agent has run at least one command (check **Hide logs** / expand logs and look for `[command]` lines).
3. Click **Start capture** for that sandbox. The button should change to “Recording (0 steps)” then “Recording (1 steps)”, etc., as the agent runs.
4. After 15–30 seconds, click **Stop & save**. Enter a name (e.g. “Add five foods”) and click **Save**.
5. You should see a green message like “Recorded N step(s). Template saved.” and the new template in the **Template (replay)** dropdown.

### D. Replay (template)

1. In the launch form, set **Template (replay)** to the template you just saved (e.g. “Add five foods”).
2. Launch a **new** sandbox (same preset). The agent runs in **replay mode**: it fetches the template steps and runs each command in order (no LLM). Stored commands are rewritten to use the **new** sandbox URL, so they hit the new container, not the old one.
3. In logs you should see “Replay mode” and the replayed commands. The app (e.g. Favorite Foods) should show the new data from the replayed requests.

### E. Scenario

1. In **Scenarios**, set name “Food demo”, preset **Favorite Foods**, default goal “Add a new food every 10 seconds.” Click **Create scenario**.
2. In the launch form, set **Scenario** to “Food demo”. Preset and goal should be filled.
3. Launch a sandbox; it should start with that preset and goal.

---

## 4. Summary

| Feature       | Purpose |
|---------------|--------|
| **Config**    | Env vars for the container (optional per launch). |
| **Expires in**| Time-to-live for the sandbox; Expires column shows it when set. |
| **Capture**   | Record agent command/output steps while a sandbox is running. |
| **Templates** | Saved walkthroughs; replay = run those steps in order (no LLM). |
| **Scenarios** | Named preset + default goal (and optional config/template) for quick launch. |

Use this guide to test each feature and to explain the product in a demo or submission.
