"""
DemoForge agent: one long-running process per sandbox (spawned by the orchestrator).

The agent asks the LLM what shell command to run next; it executes that command (e.g. curl
to hit the sandbox API) and feeds the output back to the LLM. No hardcoded API calls—
the LLM decides the exact commands (e.g. "curl -X POST http://127.0.0.1:PORT/add -d '{\"food\":\"Pizza\"}'").

Flow:
  1. LLM is given the goal and sandbox base URL. It replies with one line: a shell command, or DONE.
  2. Agent runs the command (subprocess, timeout), captures stdout/stderr.
  3. Agent sends the output back to the LLM; LLM replies with next command or DONE.
  4. Repeat. After DONE or max steps, sleep DEMOFORGE_AGENT_INTERVAL seconds and start again (persistent loop).

Env: DEMOFORGE_SANDBOX_ID, DEMOFORGE_PORT, DEMOFORGE_GOAL, DEMOFORGE_ORCHESTRATOR_URL (for logging). On Destroy, process gets SIGTERM.
"""
import os
import re
import signal
import subprocess
import sys
import time

try:
    import ollama
    HAS_OLLAMA = True
except ImportError:
    HAS_OLLAMA = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "phi3:mini")
INTERVAL_SEC = int(os.environ.get("DEMOFORGE_AGENT_INTERVAL", "10"))
COMMAND_TIMEOUT = int(os.environ.get("DEMOFORGE_COMMAND_TIMEOUT", "15"))
MAX_STEPS_PER_ROUND = int(os.environ.get("DEMOFORGE_MAX_STEPS", "10"))
ORCHESTRATOR_URL = os.environ.get("DEMOFORGE_ORCHESTRATOR_URL", "").rstrip("/")

_running = True
_sandbox_id = ""


def _stop(sig, frame):
    global _running
    _running = False


signal.signal(signal.SIGTERM, _stop)
signal.signal(signal.SIGINT, _stop)


def _log(kind: str, message: str) -> None:
    """Send log to orchestrator and print to stderr so it appears in terminal."""
    line = f"[{kind}] {message[:500]}"
    print(line, file=sys.stderr, flush=True)
    if HAS_REQUESTS and ORCHESTRATOR_URL and _sandbox_id:
        try:
            requests.post(
                f"{ORCHESTRATOR_URL}/agent-log",
                json={"sandbox_id": _sandbox_id, "type": kind, "message": message},
                timeout=2,
            )
        except Exception:
            pass


def _run_command(cmd: str) -> tuple[int, str, str]:
    """Run a shell command. Returns (returncode, stdout, stderr)."""
    cmd = cmd.strip()
    if not cmd:
        return 0, "", ""
    try:
        out = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT,
            cwd=os.path.expanduser("~"),
        )
        return out.returncode, (out.stdout or ""), (out.stderr or "")
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {COMMAND_TIMEOUT}s"
    except Exception as e:
        return -1, "", str(e)


def _parse_command(reply: str) -> str:
    """Extract the shell command from LLM reply. Handles markdown code blocks (full or unclosed)."""
    raw = reply.strip()
    if not raw:
        return ""

    # If reply is only "```shell" or "```" or similar, nothing to run
    if re.match(r"^```\s*\w*\s*$", raw):
        return ""

    # Extract from ```language\ncontent\n``` or ```language\ncontent (no closing)
    m = re.search(r"```(?:\w+)?\s*\n(.*?)(?:```|$)", raw, re.DOTALL | re.IGNORECASE)
    if m:
        block = m.group(1).strip()
        # First line that looks like a command (curl, http, etc.)
        for line in block.split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and (line.startswith("curl") or "http" in line or "/" in line):
                return line
        return block.split("\n")[0].strip() if block else ""

    # Inline `command` or plain one-line command
    m = re.search(r"`([^`]+)`", raw)
    if m:
        return m.group(1).strip()
    # Plain first line if it looks like a command
    first = raw.split("\n")[0].strip()
    if first.startswith("```") or first.lower() in ("shell", "bash", "sh"):
        return ""
    return first


FALLBACK_FOODS = ["Pizza", "Sushi", "Tacos", "Sigma", "Aura", "Vibes", "Waffles", "Curry", "Salad", "Soup", "Burger"]


def _fallback_curl_add(base_url: str) -> str:
    """When Ollama model is missing, return a curl command to add a food so the demo still works."""
    food = FALLBACK_FOODS[int(time.time()) % len(FALLBACK_FOODS)]
    # Escape for shell: double quotes inside single-quoted JSON
    return f"curl -s -X POST {base_url}/add -H 'Content-Type: application/json' -d '{{\"food\":\"{food}\"}}'"


def _ask_llm(messages: list[dict], base_url: str = "") -> str:
    """Send messages to Ollama, return full assistant content (so we can parse code blocks). On model not found, return fallback curl."""
    if not HAS_OLLAMA:
        return _fallback_curl_add(base_url) if base_url else "DONE"
    try:
        r = ollama.chat(model=OLLAMA_MODEL, messages=messages)
        text = (r.get("message") or {}).get("content", "").strip()
        return text if text else "DONE"
    except Exception as e:
        err_msg = str(e)
        _log("error", f"Ollama error: {err_msg}")
        # Model not found (404) or similar: run fallback curl so the demo still adds foods
        if base_url and ("not found" in err_msg.lower() or "404" in err_msg):
            _log("info", "Using fallback: curl to add a food (pull model with: ollama pull phi3:mini)")
            return _fallback_curl_add(base_url)
        return "DONE"


def main() -> None:
    global _sandbox_id
    _sandbox_id = os.environ.get("DEMOFORGE_SANDBOX_ID", "")
    port = os.environ.get("DEMOFORGE_PORT", "8501")
    goal = os.environ.get("DEMOFORGE_GOAL", "Interact with the sandbox to fulfill the user's goal.")
    base_url = f"http://127.0.0.1:{port}"

    _log("info", f"Agent started. Goal: {goal}. Sandbox at {base_url}. Ollama: {HAS_OLLAMA}")

    system = (
        f"You are an agent controlling a sandbox app. The app is at {base_url}.\n"
        f"Goal: {goal}\n\n"
        "To add a food, POST to {base_url}/add with JSON body. Example: "
        f"curl -X POST {base_url}/add -H 'Content-Type: application/json' -d '{{\"food\":\"Pizza\"}}'\n\n"
        "CRITICAL: Reply with ONLY one line - either the exact shell command (e.g. curl ...) or the word DONE. "
        "Do NOT use markdown, backticks, or code blocks. Output the raw command only."
    )
    messages = [{"role": "system", "content": system}]

    while _running:
        messages.append({"role": "user", "content": "What command do you run next? (one line: command or DONE)"})
        _log("info", "Asking LLM for next command...")

        for step in range(MAX_STEPS_PER_ROUND):
            reply = _ask_llm(messages, base_url=base_url)
            messages.append({"role": "assistant", "content": reply})
            _log("llm", f"Reply: {reply}")

            cmd = _parse_command(reply) or reply.strip()
            # Reject markdown leftovers or invalid commands; use fallback so demo keeps working
            if not cmd or re.match(r"^\s*DONE\s*$", cmd, re.IGNORECASE):
                _log("info", "LLM said DONE, sleeping.")
                break
            if cmd.startswith("```") or cmd.lower() in ("shell", "bash", "sh"):
                _log("info", "LLM returned only markdown/language tag; using fallback curl.")
                cmd = _fallback_curl_add(base_url)
            elif not (cmd.startswith("curl") or "http" in cmd or "/" in cmd):
                _log("info", "Reply doesn't look like a command; using fallback curl.")
                cmd = _fallback_curl_add(base_url)

            _log("command", f"Running: {cmd}")
            code, stdout, stderr = _run_command(cmd)
            output = f"exit={code}\nstdout:\n{stdout}\nstderr:\n{stderr}"
            _log("output", output[:800])
            messages.append({"role": "user", "content": f"Command output:\n{output}\nWhat's next? (one line: command or DONE)"})

        time.sleep(INTERVAL_SEC)
        messages = [{"role": "system", "content": system}]


if __name__ == "__main__":
    main()
