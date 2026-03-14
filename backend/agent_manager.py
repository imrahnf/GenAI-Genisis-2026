"""Manages per-sandbox agent processes: spawn, track, kill."""
import os
import socket
import subprocess
import sys
from typing import Any

import psutil


def _port_is_free(port: int) -> bool:
    """Return True if the port is not bound on 0.0.0.0 (so Docker can use it)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("0.0.0.0", port))
            return True
    except OSError:
        return False


class AgentManager:
    def __init__(self, port_start: int, port_end: int):
        self._port_start = port_start
        self._port_end = port_end
        self._used_ports: set[int] = set()
        self._agents: dict[str, dict[str, Any]] = {}  # sandbox_id -> {pid, port, goal, ...}

    def allocate_port(self) -> int | None:
        """Return a port that is free on the host and not already allocated. Skips in-use ports."""
        for p in range(self._port_start, self._port_end + 1):
            if p in self._used_ports:
                continue
            if not _port_is_free(p):
                continue
            self._used_ports.add(p)
            return p
        return None

    def release_port(self, port: int) -> None:
        self._used_ports.discard(port)

    def spawn(self, sandbox_id: str, port: int, goal: str, orchestrator_url: str | None = None, template_id: str | None = None) -> bool:
        """Start agent.py as subprocess. Returns True if started. If template_id set, agent runs in replay mode."""
        if sandbox_id in self._agents:
            return False
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        agent_script = os.path.join(backend_dir, "agent.py")
        env = os.environ.copy()
        env["DEMOFORGE_SANDBOX_ID"] = sandbox_id
        env["DEMOFORGE_PORT"] = str(port)
        env["DEMOFORGE_GOAL"] = goal
        if orchestrator_url:
            env["DEMOFORGE_ORCHESTRATOR_URL"] = orchestrator_url
        if template_id:
            env["DEMOFORGE_TEMPLATE_ID"] = template_id
        try:
            proc = subprocess.Popen(
                [sys.executable, agent_script],
                env=env,
                cwd=backend_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._agents[sandbox_id] = {
                "pid": proc.pid,
                "port": port,
                "goal": goal,
            }
            return True
        except Exception:
            return False

    def kill(self, sandbox_id: str) -> bool:
        """Terminate agent process and release port. Returns True if found and killed."""
        info = self._agents.pop(sandbox_id, None)
        if not info:
            return False
        pid = info["pid"]
        port = info["port"]
        self.release_port(port)
        try:
            p = psutil.Process(pid)
            p.terminate()
            p.wait(timeout=5)
        except (psutil.NoSuchProcess, psutil.TimeoutExpired):
            try:
                p.kill()
            except Exception:
                pass
        return True

    def list_active(self) -> list[dict[str, Any]]:
        result = []
        for sandbox_id, info in list(self._agents.items()):
            pid = info["pid"]
            try:
                p = psutil.Process(pid)
                if p.is_running():
                    result.append({
                        "sandbox_id": sandbox_id,
                        "pid": pid,
                        "port": info["port"],
                        "goal": info["goal"],
                    })
                else:
                    self._agents.pop(sandbox_id, None)
                    self.release_port(info["port"])
            except psutil.NoSuchProcess:
                self._agents.pop(sandbox_id, None)
                self.release_port(info["port"])
        return result

    def get(self, sandbox_id: str) -> dict[str, Any] | None:
        return self._agents.get(sandbox_id)
