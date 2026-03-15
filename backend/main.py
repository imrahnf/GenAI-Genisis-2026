"""
DemoForge orchestrator: launch/destroy sandboxes and agents.
"""
import json
import os
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager

from agent_manager import AgentManager
from config import (
    get_image_for_preset,
    ORCHESTRATOR_URL,
    PORT_RANGE_END,
    PORT_RANGE_START,
    TAILSCALE_IP,
)

# Sandboxes dir: repo root / sandboxes (backend is in repo/backend)
_SANDBOXES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sandboxes")
_MANIFEST_CACHE: dict[str, dict] = {}


def _load_backend_env() -> None:
    """Load backend/.env into process env so OPENAI_* etc. are available on startup."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        # Ignore .env parse errors; fallback to existing environment.
        pass


def _load_manifest(preset: str) -> dict | None:
    """Load manifest.json for preset. Cached in memory. Returns None if missing or invalid."""
    if preset in _MANIFEST_CACHE:
        return _MANIFEST_CACHE[preset]
    path = os.path.join(_SANDBOXES_DIR, preset, "manifest.json")
    if not os.path.isfile(path):
        _MANIFEST_CACHE[preset] = None
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        _MANIFEST_CACHE[preset] = data
        return data
    except (json.JSONDecodeError, OSError):
        _MANIFEST_CACHE[preset] = None
        return None


def _cleanup_orphan_containers():
    """Stop and remove any demoforge-* containers left from a previous backend run (frees ports)."""
    try:
        docker = get_docker()
        for c in docker.containers.list(all=True):
            if c.name and c.name.startswith("demoforge-"):
                try:
                    c.stop(timeout=3)
                except Exception:
                    try:
                        c.kill()
                    except Exception:
                        pass
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: clean up orphan containers so ports are free
    _cleanup_orphan_containers()
    yield
    # Shutdown: stop all containers we know about and kill agents
    manager = get_agent_manager()
    for sandbox_id in list(_containers.keys()):
        manager.kill(sandbox_id)
        try:
            docker = get_docker()
            c = docker.containers.get(f"demoforge-{sandbox_id}")
            c.stop(timeout=2)
        except Exception:
            try:
                docker = get_docker()
                c = docker.containers.get(f"demoforge-{sandbox_id}")
                c.kill()
            except Exception:
                pass
    _containers.clear()


app = FastAPI(title="DemoForge Orchestrator", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Docker client and agent manager (lazy init to avoid import errors if docker not running)
_docker = None
_agent_manager: AgentManager | None = None
_containers: dict[str, str] = {}  # sandbox_id -> container_id
_agent_logs: dict[str, list[dict]] = {}  # sandbox_id -> [{ts, type, message}, ...], max 200
_sandbox_meta: dict[str, dict] = {}  # sandbox_id -> {preset, config, goal, expires_at, template_id?}
_capture_active: dict[str, bool] = {}
_capture_steps: dict[str, list[dict]] = {}  # sandbox_id -> [{command, output}, ...]
_templates: dict[str, dict] = {}  # template_id -> {name, steps, preset?}
MAX_AGENT_LOG_LINES = 200
MAX_LIFECYCLE_EVENTS = 500
_lifecycle_events: list[dict] = []  # append-only event log for graph UI


def _emit_lifecycle_event(
    event_type: str,
    sandbox_id: str | None = None,
    template_id: str | None = None,
    preset: str | None = None,
    label: str | None = None,
) -> None:
    ev = {
        "id": str(uuid.uuid4())[:8],
        "type": event_type,
        "ts": time.time(),
        "sandbox_id": sandbox_id,
        "template_id": template_id,
        "preset": preset,
        "label": label,
    }
    _lifecycle_events.append(ev)
    if len(_lifecycle_events) > MAX_LIFECYCLE_EVENTS:
        _lifecycle_events[:] = _lifecycle_events[-MAX_LIFECYCLE_EVENTS:]

# Ensure backend/.env (if present) populates env before we derive LLM config.
_load_backend_env()

# Runtime LLM backend: agents fetch this so switching mid-run takes effect.
# provider: "ibm_watson" when use_remote False (placeholder; still uses Ollama until IBM wired); "openai_compatible" when True.
_llm_config = {
    "use_remote": bool(os.environ.get("OPENAI_COMPATIBLE_BASE")),
    "base": (os.environ.get("OPENAI_COMPATIBLE_BASE") or "").strip().rstrip("/"),
    "model": (os.environ.get("OPENAI_COMPATIBLE_MODEL") or "").strip(),
    "api_key": (os.environ.get("OPENAI_COMPATIBLE_API_KEY") or "").strip(),
    "provider": "ibm_watson",
}


def get_docker():
    global _docker
    if _docker is None:
        import os
        # If DOCKER_HOST not set, try Colima socket (macOS CLI Docker without Desktop)
        if "DOCKER_HOST" not in os.environ:
            for path in (
                os.path.expanduser("~/.colima/default/docker.sock"),
                os.path.expanduser("~/.colima/docker.sock"),
            ):
                if os.path.exists(path):
                    os.environ["DOCKER_HOST"] = f"unix://{path}"
                    break
        from docker import from_env
        _docker = from_env()
    return _docker


def get_agent_manager() -> AgentManager:
    global _agent_manager
    if _agent_manager is None:
        _agent_manager = AgentManager(PORT_RANGE_START, PORT_RANGE_END)
    return _agent_manager


class LaunchRequest(BaseModel):
    preset: str = "preset"  # "preset" | "bank"
    goal: str = "Add a new food every 10 seconds."
    config: dict | None = None
    expires_in: int | None = None  # seconds until auto-destroy
    template_id: str | None = None  # replay mode
    init_goal: str | None = None  # run once when container is up, then goal runs continuously


class AgentLogRequest(BaseModel):
    sandbox_id: str
    type: str = "info"  # info, llm, command, output, error
    message: str


class CaptureStopRequest(BaseModel):
    save_as_template: bool = False
    name: str = "Unnamed template"


class LLMConfigUpdate(BaseModel):
    use_remote: bool | None = None
    base: str | None = None
    model: str | None = None
    api_key: str | None = None


def _llm_provider() -> str:
    """Return provider label: ibm_watson when local, openai_compatible when remote. Placeholder for future IBM watsonx."""
    return "openai_compatible" if _llm_config["use_remote"] else "ibm_watson"


@app.get("/llm-config")
def get_llm_config():
    """Current LLM backend; agents fetch this so toggling takes effect mid-run."""
    _llm_config["provider"] = _llm_provider()
    return {
        "use_remote": _llm_config["use_remote"],
        "base": _llm_config["base"],
        "model": _llm_config["model"],
        "api_key": _llm_config["api_key"],
        "provider": _llm_config["provider"],
    }


@app.patch("/llm-config")
def update_llm_config(req: LLMConfigUpdate):
    """Set LLM backend (local vs remote). Affects all agents on their next LLM call."""
    global _llm_config
    if req.use_remote is not None:
        _llm_config["use_remote"] = req.use_remote
    if req.base is not None:
        _llm_config["base"] = req.base.strip().rstrip("/")
    if req.model is not None:
        _llm_config["model"] = req.model.strip()
    if req.api_key is not None:
        _llm_config["api_key"] = req.api_key.strip()
    return get_llm_config()


def _get_docker_or_raise():
    """Get Docker client or raise HTTPException with a clear message if Docker isn't available."""
    try:
        return get_docker()
    except Exception as e:
        msg = str(e)
        if "No such file or directory" in msg or "Connection" in msg or "docker.sock" in msg.lower():
            raise HTTPException(
                status_code=503,
                detail="Docker is not running. Start Docker Desktop (or the Docker daemon), then try again.",
            )
        raise HTTPException(status_code=503, detail=f"Docker unavailable: {msg}")


def _env_from_config(config: dict | None) -> dict[str, str] | None:
    """Build env dict for container; all values as strings so Docker receives them."""
    if not config:
        return None
    return {k: str(v) for k, v in config.items() if v is not None}


@app.post("/launch")
def launch(request: Request, req: LaunchRequest):
    """Start preset container + agent; return sandbox URL."""
    # Agent runs on same host; use 127.0.0.1 so template fetch and agent-log always work
    backend_port = getattr(request.url, "port", None) or 8000
    agent_orchestrator_url = f"http://127.0.0.1:{backend_port}"
    preset = req.preset
    goal = req.goal
    config = req.config
    template_id = req.template_id
    expires_in = req.expires_in
    init_goal = (req.init_goal or "").strip() or None

    image = get_image_for_preset(preset)
    if not image:
        raise HTTPException(status_code=400, detail=f"Unknown preset: {preset}")

    sandbox_id = str(uuid.uuid4())[:8]
    manager = get_agent_manager()
    port = manager.allocate_port()
    if port is None:
        raise HTTPException(status_code=503, detail="No ports available")

    expiry_at = (time.time() + expires_in) if expires_in else None
    env_dict = _env_from_config(config)

    docker = _get_docker_or_raise()
    try:
        container = docker.containers.run(
            image,
            detach=True,
            ports={"8501/tcp": port},
            name=f"demoforge-{sandbox_id}",
            remove=True,
            environment=env_dict,
        )
        container_id = container.id if hasattr(container, "id") else str(container)
        _containers[sandbox_id] = container_id
    except Exception as e:
        manager.release_port(port)
        err_msg = str(e)
        if "404" in err_msg or "pull access denied" in err_msg or "not found" in err_msg.lower():
            raise HTTPException(
                status_code=503,
                detail=f"Image {image} not found. Build it from the project root (where sandboxes/ is): "
                f"docker build -t {image} sandboxes/{preset}/  or run ./build_sandboxes.sh",
            )
        raise HTTPException(status_code=500, detail=f"Container start failed: {e}")

    if not manager.spawn(
        sandbox_id, port, goal,
        orchestrator_url=agent_orchestrator_url,
        template_id=template_id,
        preset=preset,
        init_goal=init_goal,
    ):
        try:
            c = docker.containers.get(f"demoforge-{sandbox_id}")
            c.stop()
        except Exception:
            pass
        manager.release_port(port)
        _containers.pop(sandbox_id, None)
        raise HTTPException(status_code=500, detail="Agent spawn failed")

    _agent_logs[sandbox_id] = []
    _sandbox_meta[sandbox_id] = {
        "preset": preset,
        "config": config or {},
        "goal": goal,
        "expires_at": expiry_at,
        "template_id": template_id,
        "init_goal": init_goal,
    }
    _emit_lifecycle_event(
        "launch",
        sandbox_id=sandbox_id,
        preset=preset,
        template_id=template_id,
        label=(goal[:40] + "…") if goal and len(goal) > 40 else (goal or None),
    )
    url = f"http://{TAILSCALE_IP}:{port}"
    return {
        "sandbox_id": sandbox_id,
        "url": url,
        "port": port,
        "preset": preset,
        "expires_at": expiry_at,
    }


@app.post("/agent-log")
def agent_log(req: AgentLogRequest):
    """Agent calls this to append a log line. When capture is active, pair command+output for templates."""
    sid = req.sandbox_id
    if sid not in _agent_logs:
        _agent_logs[sid] = []
    _agent_logs[sid].append({
        "ts": time.time(),
        "type": req.type,
        "message": req.message[:2000],
    })
    if len(_agent_logs[sid]) > MAX_AGENT_LOG_LINES:
        _agent_logs[sid] = _agent_logs[sid][-MAX_AGENT_LOG_LINES:]

    if _capture_active.get(sid):
        if sid not in _capture_steps:
            _capture_steps[sid] = []
        log_type = (req.type or "").strip().lower()
        if log_type == "command":
            raw = req.message[:2000].strip()
            for prefix in ("Running: ", "Replay: ", "Init: "):
                if raw.startswith(prefix):
                    raw = raw[len(prefix):].strip()
                    break
            # Strip deterministic loop labels so stored command is just the curl (replay-friendly)
            if "curl" in raw and raw.find("curl") > 0:
                raw = raw[raw.find("curl"):].strip()
            _capture_steps[sid].append({"command": raw, "output": ""})
        elif log_type == "output" and _capture_steps[sid]:
            _capture_steps[sid][-1]["output"] = req.message[:2000]

    return {"ok": True}


@app.post("/destroy/{sandbox_id}")
def destroy(sandbox_id: str):
    """Stop container and kill agent. Always releases port."""
    _emit_lifecycle_event("destroy", sandbox_id=sandbox_id)
    manager = get_agent_manager()
    manager.kill(sandbox_id)
    _containers.pop(sandbox_id, None)
    _agent_logs.pop(sandbox_id, None)
    _sandbox_meta.pop(sandbox_id, None)
    _capture_active.pop(sandbox_id, None)
    _capture_steps.pop(sandbox_id, None)
    # Force-stop container
    try:
        docker = _get_docker_or_raise()
        c = docker.containers.get(f"demoforge-{sandbox_id}")
        c.stop(timeout=3)
    except Exception:
        try:
            docker = _get_docker_or_raise()
            c = docker.containers.get(f"demoforge-{sandbox_id}")
            c.kill()
        except Exception:
            pass
    return {"status": "destroyed", "sandbox_id": sandbox_id}


@app.post("/reset/{sandbox_id}")
def reset(sandbox_id: str, request: Request):
    """Destroy current sandbox and launch a new one with same preset/config/goal/template."""
    meta = _sandbox_meta.get(sandbox_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    _emit_lifecycle_event("destroy", sandbox_id=sandbox_id)
    preset = meta["preset"]
    config = meta.get("config") or {}
    goal = meta["goal"]
    template_id = meta.get("template_id")
    _destroy_sandbox(sandbox_id)
    init_goal = meta.get("init_goal")
    req = LaunchRequest(preset=preset, goal=goal, config=config, expires_in=None, template_id=template_id, init_goal=init_goal)
    return launch(request, req)


@app.post("/capture/start/{sandbox_id}")
def capture_start(sandbox_id: str):
    if sandbox_id not in _containers:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    _capture_active[sandbox_id] = True
    _capture_steps[sandbox_id] = []
    _emit_lifecycle_event("capture_start", sandbox_id=sandbox_id)
    return {"ok": True, "capture_active": True}


@app.post("/capture/stop/{sandbox_id}")
def capture_stop(sandbox_id: str, req: CaptureStopRequest):
    _capture_active[sandbox_id] = False
    steps = _capture_steps.get(sandbox_id, [])
    steps_copy = [{"command": s.get("command", ""), "output": s.get("output", "")} for s in steps]
    _capture_steps[sandbox_id] = []

    template_id = None
    template_name = None
    if req.save_as_template:
        template_id = str(uuid.uuid4())[:8]
        meta = _sandbox_meta.get(sandbox_id, {})
        preset = meta.get("preset", "preset")
        template_name = (req.name or "Unnamed").strip() or "Unnamed"
        _templates[template_id] = {
            "name": template_name,
            "preset": preset,
            "steps": steps_copy,
        }
    _emit_lifecycle_event(
        "capture_stop",
        sandbox_id=sandbox_id,
        template_id=template_id,
        label=template_name,
    )
    message = "Capture stopped."
    if req.save_as_template:
        message = f"Template saved with {len(steps_copy)} step(s). Use it in 'Template (replay)' and launch a new sandbox." if steps_copy else (
            "Template saved with 0 steps. Set ORCHESTRATOR_URL to match backend URL so the agent can post logs; then capture again."
        )
    return {
        "ok": True,
        "template_id": template_id,
        "steps_recorded": len(steps_copy),
        "message": message,
    }


# Fallback when manifest missing
PRESET_META = {
    "preset": {"name": "Favorite Foods", "description": "Flask app with synthetic food list; agent can add items via API."},
    "bank": {"name": "Bank", "description": "Mini banking demo: accounts and transfers, synthetic data only."},
    "spending": {"name": "Spending & Anomaly Tracker", "description": "Single-user spending tracker with anomaly detection; synthetic data only."},
}


@app.get("/context/{preset}")
def get_context(preset: str):
    """Return manifest for preset. Agent fetches this to build context-aware prompts."""
    from config import get_image_for_preset
    if not get_image_for_preset(preset):
        raise HTTPException(status_code=404, detail="Unknown preset")
    manifest = _load_manifest(preset)
    if not manifest:
        return {"id": preset, "name": PRESET_META.get(preset, {}).get("name", preset), "description": PRESET_META.get(preset, {}).get("description", "")}
    return manifest


@app.get("/presets")
def list_presets():
    """List presets with manifest-derived summary (capabilities, defaults) for UI."""
    from config import PRESETS
    out = []
    for pid in PRESETS:
        m = _load_manifest(pid)
        meta = PRESET_META.get(pid, {})
        entry = {
            "id": pid,
            "name": (m or {}).get("name") or meta.get("name", pid),
            "description": (m or {}).get("description") or meta.get("description", ""),
        }
        if m:
            if m.get("synthetic_data"):
                entry["synthetic_data"] = m["synthetic_data"]
            if m.get("endpoints"):
                entry["capabilities"] = [f"{e.get('method', 'GET')} {e.get('path', '')}" for e in m["endpoints"]]
            if m.get("default_goal"):
                entry["default_goal"] = m["default_goal"]
            if m.get("default_config"):
                entry["default_config"] = m["default_config"]
            if m.get("config_schema"):
                entry["config_schema"] = m["config_schema"]
        out.append(entry)
    return {"presets": out}


@app.get("/templates")
def list_templates():
    return {
        "templates": [
            {
                "id": tid,
                "name": t.get("name", tid),
                "preset": t.get("preset", "preset"),
                "steps_count": len(t.get("steps", [])),
            }
            for tid, t in _templates.items()
        ]
    }


@app.get("/templates/{template_id}")
def get_template(template_id: str):
    if template_id not in _templates:
        raise HTTPException(status_code=404, detail="Template not found")
    t = _templates[template_id]
    return {"id": template_id, "name": t["name"], "steps": t["steps"]}


def _destroy_sandbox(sandbox_id: str) -> None:
    manager = get_agent_manager()
    manager.kill(sandbox_id)
    _containers.pop(sandbox_id, None)
    _agent_logs.pop(sandbox_id, None)
    _sandbox_meta.pop(sandbox_id, None)
    _capture_active.pop(sandbox_id, None)
    _capture_steps.pop(sandbox_id, None)
    try:
        docker = _get_docker_or_raise()
        c = docker.containers.get(f"demoforge-{sandbox_id}")
        c.stop(timeout=3)
    except Exception:
        try:
            docker = _get_docker_or_raise()
            c = docker.containers.get(f"demoforge-{sandbox_id}")
            c.kill()
        except Exception:
            pass


@app.get("/lifecycle-events")
def lifecycle_events(limit: int | None = None):
    """Return lifecycle event log for the graph UI. Optional ?limit=N."""
    events = list(_lifecycle_events)
    if limit is not None and limit > 0:
        events = events[-limit:]
    return {"events": events}


@app.get("/status")
def status():
    """List active sandboxes. Destroy any that are past expires_at."""
    now = time.time()
    to_destroy = [sid for sid, meta in _sandbox_meta.items() if meta.get("expires_at") and meta["expires_at"] < now]
    for sid in to_destroy:
        _destroy_sandbox(sid)

    manager = get_agent_manager()
    active = manager.list_active()
    out = []
    for a in active:
        sid = a["sandbox_id"]
        meta = _sandbox_meta.get(sid, {})
        url = f"http://{TAILSCALE_IP}:{a['port']}"
        steps = _capture_steps.get(sid, [])
        out.append({
            "sandbox_id": sid,
            "url": url,
            "port": a["port"],
            "goal": a["goal"],
            "preset": meta.get("preset", "preset"),
            "template_id": meta.get("template_id"),  # set when launched with Template (replay)
            "expires_at": meta.get("expires_at"),
            "capture_active": _capture_active.get(sid, False),
            "capture_steps_count": len(steps),
            "logs": _agent_logs.get(sid, []),
        })
    return {"sandboxes": out}
