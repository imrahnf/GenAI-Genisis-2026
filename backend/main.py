"""
DemoForge orchestrator: launch/destroy sandboxes and agents.
"""
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager

from agent_manager import AgentManager
from config import (
    ORCHESTRATOR_URL,
    PORT_RANGE_END,
    PORT_RANGE_START,
    PRESET_IMAGE,
    TAILSCALE_IP,
)


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
MAX_AGENT_LOG_LINES = 200


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
    goal: str = "Add a new food every 10 seconds."
    config: dict | None = None


class AgentLogRequest(BaseModel):
    sandbox_id: str
    type: str = "info"  # info, llm, command, output, error
    message: str


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


@app.post("/launch")
def launch(req: LaunchRequest):
    """Start preset container + agent; return sandbox URL."""
    sandbox_id = str(uuid.uuid4())[:8]
    manager = get_agent_manager()
    port = manager.allocate_port()
    if port is None:
        raise HTTPException(status_code=503, detail="No ports available")
    docker = _get_docker_or_raise()
    try:
        container = docker.containers.run(
            PRESET_IMAGE,
            detach=True,
            ports={"8501/tcp": port},
            name=f"demoforge-{sandbox_id}",
            remove=True,
        )
        container_id = container.id if hasattr(container, "id") else str(container)
        _containers[sandbox_id] = container_id
    except Exception as e:
        manager.release_port(port)
        raise HTTPException(status_code=500, detail=f"Container start failed: {e}")
    if not manager.spawn(sandbox_id, port, req.goal, orchestrator_url=ORCHESTRATOR_URL):
        try:
            c = docker.containers.get(f"demoforge-{sandbox_id}")
            c.stop()
        except Exception:
            pass
        manager.release_port(port)
        _containers.pop(sandbox_id, None)
        raise HTTPException(status_code=500, detail="Agent spawn failed")
    _agent_logs[sandbox_id] = []
    url = f"http://{TAILSCALE_IP}:{port}"
    return {"sandbox_id": sandbox_id, "url": url, "port": port}


@app.post("/agent-log")
def agent_log(req: AgentLogRequest):
    """Agent calls this to append a log line (thinking process, commands, output)."""
    import time
    if req.sandbox_id not in _agent_logs:
        _agent_logs[req.sandbox_id] = []
    _agent_logs[req.sandbox_id].append({
        "ts": time.time(),
        "type": req.type,
        "message": req.message[:2000],
    })
    if len(_agent_logs[req.sandbox_id]) > MAX_AGENT_LOG_LINES:
        _agent_logs[req.sandbox_id] = _agent_logs[req.sandbox_id][-MAX_AGENT_LOG_LINES:]
    return {"ok": True}


@app.post("/destroy/{sandbox_id}")
def destroy(sandbox_id: str):
    """Stop container and kill agent. Always releases port."""
    manager = get_agent_manager()
    manager.kill(sandbox_id)  # kill agent process and release port
    _containers.pop(sandbox_id, None)
    _agent_logs.pop(sandbox_id, None)
    # Force-stop container so port is freed even if we lost track of it
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


@app.get("/status")
def status():
    """List active sandboxes with URL and goal."""
    manager = get_agent_manager()
    active = manager.list_active()
    out = []
    for a in active:
        sid = a["sandbox_id"]
        url = f"http://{TAILSCALE_IP}:{a['port']}"
        out.append({
            "sandbox_id": sid,
            "url": url,
            "port": a["port"],
            "goal": a["goal"],
            "logs": _agent_logs.get(sid, []),
        })
    return {"sandboxes": out}
