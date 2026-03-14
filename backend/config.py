"""DemoForge backend configuration."""
import os
import subprocess

# Tailscale IP (Mac Pro) for shareable sandbox URLs
def _get_tailscale_ip() -> str:
    try:
        out = subprocess.check_output(
            ["tailscale", "ip", "-4"],
            text=True,
            timeout=2,
        )
        return out.strip() or "127.0.0.1"
    except Exception:
        return os.environ.get("TAILSCALE_IP", "127.0.0.1")

TAILSCALE_IP = _get_tailscale_ip()
PORT_RANGE_START = 8501
PORT_RANGE_END = 8600
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "phi3:mini")
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
AGENT_WORKDIR = os.environ.get("AGENT_WORKDIR", "/tmp/demoforge")
# Preset key -> Docker image (built from sandboxes/<key>/). No registry pull at runtime.
PRESETS = {"preset": "demoforge/preset:latest", "bank": "demoforge/bank:latest"}

def get_image_for_preset(preset_key: str) -> str | None:
    return PRESETS.get(preset_key)

# URL the agent uses to POST logs (same host as orchestrator)
ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://127.0.0.1:8000")
