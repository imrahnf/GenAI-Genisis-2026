## Adding a new DemoForge preset

Use this checklist when you (or your partner) want to add a new app as a DemoForge preset.

### 1. Place the app under `sandboxes/<preset-id>/`

- Create a new directory, e.g. `sandboxes/my-app/`.
- Put all app code there (backend, static files, etc.).

### 2. Dockerfile requirements

In `sandboxes/<preset-id>/Dockerfile`:

- The container must listen on **`0.0.0.0:8501`** and expose port **8501**.
- Example (Python/Flask style):

```dockerfile
FROM python:3.11-slim

WORKDIR /app
RUN mkdir -p /data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

EXPOSE 8501
CMD ["python", "app.py"]
```

### 3. App must read env config

- The app should read configuration from environment variables so DemoForge can control behavior per launch:
  - Example: `APP_TITLE`, feature flags, etc.
- Follow the patterns used in:
  - `sandboxes/preset/app.py`
  - `sandboxes/bank/app.py`

### 4. Create `manifest.json`

In `sandboxes/<preset-id>/manifest.json`, start from the template in:

- `docs/MANIFEST_SCHEMA.md` (see the **Manifest template** section)

Fill in:

- `id` — your preset key (e.g. `"my-app"`).
- `name`, `description`, `synthetic_data`.
- `endpoints` — the main API routes the agent should use.
- `example_commands` — 1–3 `curl` examples (you can use `{{base_url}}`).
- `default_goal` — what the agent should do by default.
- `default_config` — your default env settings.
- `config_schema` — how the control panel should render config controls (text, select, boolean, etc.).

### 5. Wire the preset into the orchestrator

- In `backend/config.py`, add your preset to `PRESETS`:

```python
PRESETS = {
    "preset": "demoforge/preset:latest",
    "bank": "demoforge/bank:latest",
    "my-app": "demoforge/my-app:latest",
}
```

- The backend’s `/presets` endpoint will now include your new preset and its manifest-driven metadata for the dashboard grid.

### 6. Build the image

From the repo root:

```bash
docker build -t demoforge/my-app:latest sandboxes/my-app/
```

### 7. Test from the dashboard

- Restart the backend if it was running.
- Open the DemoForge dashboard:
  - Your new preset card should appear in the **Presets** grid.
  - Clicking it should show:
    - Manifest-derived summary (synthetic data, capabilities).
    - Config controls based on `config_schema`.
- Launch a sandbox and verify:
  - The app is reachable at the given URL.
  - Env-driven config (e.g. title/flags) behaves as expected.

