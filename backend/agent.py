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

Env: DEMOFORGE_SANDBOX_ID, DEMOFORGE_PORT, DEMOFORGE_GOAL, DEMOFORGE_ORCHESTRATOR_URL (for logging).
If DEMOFORGE_TEMPLATE_ID is set, agent runs in replay mode: fetch template steps and run commands in order (no LLM).
On Destroy, process gets SIGTERM.
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
PRESET = os.environ.get("DEMOFORGE_PRESET", "")

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


def _strip_trailing_done(cmd: str) -> str:
    """Remove trailing ' && DONE' or ' && echo DONE' so the shell doesn't try to run DONE as a command."""
    if not cmd or not cmd.strip():
        return cmd
    cmd = cmd.strip()
    for suffix in (" && DONE", " && echo DONE"):
        if cmd.endswith(suffix):
            return cmd[: -len(suffix)].strip()
    return cmd


FALLBACK_FOODS = ["Pizza", "Sushi", "Tacos", "Sigma", "Aura", "Vibes", "Waffles", "Curry", "Salad", "Soup", "Burger"]


def _fallback_curl_add(base_url: str) -> str:
    """When Ollama model is missing, return a curl command so the demo still works."""
    if PRESET == "bank":
        # Create a demo account for the bank app
        name = f"Demo{int(time.time()) % 1000}"
        return (
            f"curl -s -X POST {base_url}/api/accounts "
            f"-H 'Content-Type: application/json' "
            f"-d '{{\"name\":\"{name}\",\"initial_balance\":100}}'"
        )
    # Foods app fallback
    food = FALLBACK_FOODS[int(time.time()) % len(FALLBACK_FOODS)]
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


def _rewrite_command_for_replay(cmd: str, current_base_url: str) -> str:
    """Replace any previous sandbox URL (e.g. http://127.0.0.1:8502) in the command with current_base_url so replay hits this sandbox."""
    if not cmd or not current_base_url:
        return cmd
    # Replace old sandbox host:port with current so replayed commands hit the new container
    out = re.sub(r"http://127\.0\.0\.1:\d+", current_base_url, cmd)
    out = re.sub(r"http://localhost:\d+", current_base_url, out)
    return out


def _replay_template(template_id: str, base_url: str) -> list[dict]:
    """Fetch template steps from orchestrator. Returns list of {command, output}."""
    if not ORCHESTRATOR_URL or not HAS_REQUESTS:
        return []
    url = f"{ORCHESTRATOR_URL}/templates/{template_id}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json()
        steps = data.get("steps", [])
        return steps if isinstance(steps, list) else []
    except Exception as e:
        _log("error", f"Template fetch failed: {e}")
        return []


def _fetch_manifest(base_url: str) -> dict | None:
    """Fetch manifest for current preset from orchestrator. Returns None on failure."""
    if not PRESET or not ORCHESTRATOR_URL or not HAS_REQUESTS:
        return None
    try:
        r = requests.get(f"{ORCHESTRATOR_URL}/context/{PRESET}", timeout=5)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


def _system_prompt_from_manifest(manifest: dict, base_url: str, goal: str) -> str:
    """Build system prompt from manifest. Replaces {{base_url}} in example_commands."""
    parts = [
        f"You are an agent controlling an app. The app is at {base_url}.",
        f"Goal: {goal}",
        "",
    ]
    desc = manifest.get("description", "").strip()
    if desc:
        parts.append(desc + "\n")
    endpoints = manifest.get("endpoints", [])
    if endpoints:
        parts.append("API:")
        for e in endpoints:
            method = e.get("method", "GET")
            path = e.get("path", "")
            body = e.get("body")
            line = f"- {method} {path}"
            if body and isinstance(body, dict):
                line += f" with JSON {body}"
            line += "."
            if e.get("description"):
                line += f" {e['description']}"
            parts.append(line)
        parts.append("")
    examples = manifest.get("example_commands", [])
    if examples:
        parts.append("Example commands (use this base URL):")
        for ex in examples[:5]:
            cmd = ex.replace("{{base_url}}", base_url).strip()
            parts.append(cmd)
        parts.append("")
    parts.append(
        "CRITICAL RULES:\n"
        "- Reply with ONLY one line per turn: either a single shell command (e.g. curl ...) or the word DONE. Do NOT append '&& DONE' or '&& echo DONE' to the command.\n"
        "- If you are unsure what to do next, output DONE.\n"
        "- Use the minimal set of API calls that match the goal. If the goal is to create (a) single account(s) or run a transfer, use POST /api/accounts once per new account and POST /api/transfer; use POST /api/seed ONLY when the goal explicitly asks to seed or create many users (e.g. 'seed 100 users').\n"
        "- You may combine multiple API calls in one shell command using simple loops or &&, e.g.:\n"
        "  for i in $(seq 1 5); do curl ...; done\n"
        "- You may only use shell builtins plus curl and echo. Never use python, rm, apt, brew, or any file-system or package-manager commands.\n"
        "- Use ONLY the API endpoints and JSON shapes described above. Do NOT invent new paths or fields.\n"
        "- Do NOT use markdown, backticks, or code fences; output the raw command only."
    )
    return "\n".join(parts)


def main() -> None:
    global _sandbox_id
    _sandbox_id = os.environ.get("DEMOFORGE_SANDBOX_ID", "")
    port = os.environ.get("DEMOFORGE_PORT", "8501")
    goal = os.environ.get("DEMOFORGE_GOAL", "Interact with the sandbox to fulfill the user's goal.")
    template_id = os.environ.get("DEMOFORGE_TEMPLATE_ID", "")
    base_url = f"http://127.0.0.1:{port}"

    if template_id:
        _log("info", f"Replay mode. Template: {template_id}. Sandbox at {base_url}")
        time.sleep(3)  # give container app time to be ready
        steps = _replay_template(template_id, base_url)
        if not steps:
            _log("error", "No steps in template or failed to fetch.")
        else:
            _log("info", f"Fetched {len(steps)} steps, running replay.")
        while _running and steps:
            for step in steps:
                if not _running:
                    break
                cmd = step.get("command", "").strip()
                # Stored commands may have "Running: " or "Replay: " prefix from logging
                for prefix in ("Running: ", "Replay: "):
                    if cmd.startswith(prefix):
                        cmd = cmd[len(prefix):].strip()
                        break
                if not cmd:
                    continue
                cmd = _rewrite_command_for_replay(cmd, base_url)
                _log("command", f"Replay: {cmd}")
                code, stdout, stderr = _run_command(cmd)
                output = f"exit={code}\nstdout:\n{stdout}\nstderr:\n{stderr}"
                _log("output", output[:800])
                time.sleep(2)
            time.sleep(INTERVAL_SEC)
        return

    init_goal = os.environ.get("DEMOFORGE_INIT_GOAL", "").strip()
    _log("info", f"Agent started. Goal: {goal}. Sandbox at {base_url}. Ollama: {HAS_OLLAMA}" + (f" Init goal: {init_goal}" if init_goal else ""))

    manifest = _fetch_manifest(base_url)
    if manifest and manifest.get("endpoints"):
        system = _system_prompt_from_manifest(manifest, base_url, goal)
        _log("info", "Using manifest context for system prompt.")
    elif PRESET == "bank":
        system = (
            f"You are an agent controlling a mini banking app. The app is at {base_url}.\n"
            f"Goal: {goal}\n\n"
            "API:\n"
            "- Create account: POST /api/accounts with JSON {\"name\": \"string\", \"initial_balance\": number}.\n"
            "- Transfer: POST /api/transfer with JSON {\"from_id\": int, \"to_id\": int, \"amount\": number}.\n\n"
            f"Example create: curl -X POST {base_url}/api/accounts -H 'Content-Type: application/json' -d '{{\"name\":\"Alice\",\"initial_balance\":100}}'\n"
            f"Example transfer: curl -X POST {base_url}/api/transfer -H 'Content-Type: application/json' -d '{{\"from_id\":1,\"to_id\":2,\"amount\":10}}'\n\n"
            "CRITICAL RULES:\n"
            "- Reply with ONLY one line per turn: either a single shell command (e.g. curl ...) or the word DONE. Do NOT append '&& DONE' or '&& echo DONE' to the command.\n"
            "- If you are unsure what to do next, output DONE.\n"
            "- Use the minimal set of API calls that match the goal. For 'create an account and run a transfer' use POST /api/accounts once then POST /api/transfer; use POST /api/seed ONLY when the goal explicitly says to seed or create many users.\n"
            "- You may combine multiple API calls in one shell command using simple loops or &&, e.g.:\n"
            "  for i in $(seq 1 5); do curl ...; done\n"
            "- You may only use shell builtins plus curl and echo. Never use python, rm, apt, brew, or any file-system or package-manager commands.\n"
            "- Use ONLY the API endpoints and JSON shapes described above. Do NOT invent new paths or fields.\n"
            "- Do NOT use markdown, backticks, or code fences; output the raw command only."
        )
    else:
        system = (
            f"You are an agent controlling a favorite foods app. The app is at {base_url}.\n"
            f"Goal: {goal}\n\n"
            "To add a food, POST to /add with JSON body {\"food\":\"Pizza\"}.\n"
            f"Example: curl -X POST {base_url}/add -H 'Content-Type: application/json' -d '{{\"food\":\"Pizza\"}}'\n\n"
            "CRITICAL RULES:\n"
            "- Reply with ONLY one line per turn: either a single shell command (e.g. curl ...) or the word DONE.\n"
            "- If you are unsure what to do next, output DONE.\n"
            "- You may combine multiple API calls in one shell command using simple loops or &&, e.g.:\n"
            "  for i in $(seq 1 5); do curl ...; done\n"
            "- You may only use shell builtins plus curl and echo. Never use python, rm, apt, brew, or any file-system or package-manager commands.\n"
            "- Do NOT use markdown, backticks, or code fences; output the raw command only."
        )
    messages = [{"role": "system", "content": system}]

    # Optional init phase: run once with init_goal, then continue with main goal
    if init_goal and not template_id:
        init_system = _system_prompt_from_manifest(manifest, base_url, init_goal) if (manifest and manifest.get("endpoints")) else (
            f"You are an agent controlling an app at {base_url}. Goal: {init_goal}. Use minimal API calls. Reply with one shell command or DONE. Do NOT append && DONE."
        )
        if not (manifest and manifest.get("endpoints")):
            if PRESET == "bank":
                init_system = (
                    f"You are an agent controlling a mini banking app at {base_url}. Goal: {init_goal}. "
                    "Use POST /api/accounts for single account, POST /api/transfer for transfer. Reply with one command or DONE. Do NOT append && DONE."
                )
            else:
                init_system = (
                    f"You are an agent controlling a favorite foods app at {base_url}. Goal: {init_goal}. "
                    "Reply with one command or DONE. Do NOT append && DONE."
                )
        init_messages = [{"role": "system", "content": init_system}]
        _log("info", f"Running init phase: {init_goal}")
        for _ in range(MAX_STEPS_PER_ROUND):
            if not _running:
                break
            init_messages.append({"role": "user", "content": "What single shell command do you run next? (one line: command or DONE)"})
            reply = _ask_llm(init_messages, base_url=base_url)
            init_messages.append({"role": "assistant", "content": reply})
            cmd = _parse_command(reply) or reply.strip()
            if not cmd or re.match(r"^\s*DONE\s*$", cmd, re.IGNORECASE):
                _log("info", "Init phase DONE.")
                break
            if cmd.startswith("```") or cmd.lower() in ("shell", "bash", "sh"):
                cmd = _fallback_curl_add(base_url)
            elif not (cmd.startswith("curl") or "http" in cmd or "/" in cmd):
                cmd = _fallback_curl_add(base_url)
            cmd = _strip_trailing_done(cmd)
            _log("command", f"Init: {cmd}")
            code, stdout, stderr = _run_command(cmd)
            output = f"exit={code}\nstdout:\n{stdout}\nstderr:\n{stderr}"
            _log("output", output[:800])
            init_messages.append({"role": "user", "content": f"Command output:\n{output}\nWhat's next? (one line: command or DONE)"})
        _log("info", "Init phase complete, switching to main goal.")
        # Rebuild system for main goal (may have been manifest-based)
        if manifest and manifest.get("endpoints"):
            system = _system_prompt_from_manifest(manifest, base_url, goal)
        elif PRESET == "bank":
            system = (
                f"You are an agent controlling a mini banking app. The app is at {base_url}.\n"
                f"Goal: {goal}\n\n"
                "API:\n"
                "- Create account: POST /api/accounts with JSON {\"name\": \"string\", \"initial_balance\": number}.\n"
                "- Transfer: POST /api/transfer with JSON {\"from_id\": int, \"to_id\": int, \"amount\": number}.\n\n"
                f"Example create: curl -X POST {base_url}/api/accounts -H 'Content-Type: application/json' -d '{{\"name\":\"Alice\",\"initial_balance\":100}}'\n"
                f"Example transfer: curl -X POST {base_url}/api/transfer -H 'Content-Type: application/json' -d '{{\"from_id\":1,\"to_id\":2,\"amount\":10}}'\n\n"
                "CRITICAL RULES:\n"
                "- Reply with ONLY one line per turn: either a single shell command (e.g. curl ...) or the word DONE. Do NOT append '&& DONE' or '&& echo DONE' to the command.\n"
                "- Use the minimal set of API calls that match the goal. For 'create an account and run a transfer' use POST /api/accounts once then POST /api/transfer; use POST /api/seed ONLY when the goal explicitly says to seed or create many users.\n"
                "- You may only use shell builtins plus curl and echo. Do NOT use markdown, backticks, or code fences; output the raw command only."
            )
        else:
            system = (
                f"You are an agent controlling a favorite foods app. The app is at {base_url}.\n"
                f"Goal: {goal}\n\n"
                "To add a food, POST to /add with JSON body {\"food\":\"Pizza\"}.\n"
                "CRITICAL: Reply with ONLY one line: command or DONE. Do NOT append && DONE. Do NOT use markdown."
            )
        messages = [{"role": "system", "content": system}]

    while _running:
        messages.append({"role": "user", "content": "What single shell command do you run next? (one line: command or DONE; if unsure, output DONE)"})
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

            cmd = _strip_trailing_done(cmd)
            _log("command", f"Running: {cmd}")
            code, stdout, stderr = _run_command(cmd)
            output = f"exit={code}\nstdout:\n{stdout}\nstderr:\n{stderr}"
            _log("output", output[:800])
            messages.append({"role": "user", "content": f"Command output:\n{output}\nWhat's next? (one line: command or DONE; if unsure, output DONE)"})

        time.sleep(INTERVAL_SEC)
        messages = [{"role": "system", "content": system}]


if __name__ == "__main__":
    main()
