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
import json
import os
import random
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

try:
    from openai import OpenAI
    HAS_OPENAI_CLIENT = True
except ImportError:
    HAS_OPENAI_CLIENT = False

OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
INTERVAL_SEC = int(os.environ.get("DEMOFORGE_AGENT_INTERVAL", "3"))
COMMAND_TIMEOUT = int(os.environ.get("DEMOFORGE_COMMAND_TIMEOUT", "15"))
MAX_STEPS_PER_ROUND = int(os.environ.get("DEMOFORGE_MAX_STEPS", "10"))
# Cap LLM output length for faster CPU inference (0 = no cap).
MAX_PREDICT_TOKENS = int(os.environ.get("DEMOFORGE_AGENT_MAX_TOKENS", "256"))
ORCHESTRATOR_URL = os.environ.get("DEMOFORGE_ORCHESTRATOR_URL", "").rstrip("/")
PRESET = os.environ.get("DEMOFORGE_PRESET", "")

# Optional OpenAI-compatible remote LLM (e.g. local server, Hugging Face, vLLM).
# Use base_url like http://localhost:8000/v1 and model like openai/gpt-oss-20b; api_key can be "EMPTY" if required.
OPENAI_COMPATIBLE_BASE = os.environ.get("OPENAI_COMPATIBLE_BASE", "").rstrip("/")
OPENAI_COMPATIBLE_API_KEY = os.environ.get("OPENAI_COMPATIBLE_API_KEY", "")
OPENAI_COMPATIBLE_MODEL = os.environ.get("OPENAI_COMPATIBLE_MODEL", "")
USE_OPENAI_COMPATIBLE = bool(OPENAI_COMPATIBLE_BASE)
# If set, use the Responses API (instructions + input -> output_text) instead of chat/completions.
OPENAI_USE_RESPONSES_API = os.environ.get("OPENAI_USE_RESPONSES_API", "").strip().lower() in ("1", "true", "yes")

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


def _interval_from_goal(goal: str) -> int | None:
    """If goal mentions 'every N second(s)', return N; else None so caller uses INTERVAL_SEC."""
    if not goal:
        return None
    m = re.search(r"every\s+(\d+)\s+second", goal, re.IGNORECASE)
    return int(m.group(1)) if m else None


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


def _fetch_runtime_llm_config() -> dict | None:
    """Get current LLM backend from orchestrator so toggle takes effect mid-run. Returns None on failure."""
    if not ORCHESTRATOR_URL or not HAS_REQUESTS:
        return None
    try:
        r = requests.get(f"{ORCHESTRATOR_URL}/llm-config", timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _ask_llm(messages: list[dict], base_url: str = "", max_tokens: int = 0) -> str:
    """Call LLM (OpenAI-compatible HTTP or Ollama), return assistant content. Uses runtime config from orchestrator when available."""
    runtime = _fetch_runtime_llm_config()
    use_remote = runtime.get("use_remote") if isinstance(runtime, dict) else USE_OPENAI_COMPATIBLE
    base = (runtime.get("base") or "").strip().rstrip("/") if isinstance(runtime, dict) else OPENAI_COMPATIBLE_BASE
    if not base and USE_OPENAI_COMPATIBLE:
        base = OPENAI_COMPATIBLE_BASE
    if isinstance(runtime, dict) and runtime.get("use_remote") is False:
        use_remote = False
    model = (runtime.get("model") or "").strip() if isinstance(runtime, dict) else (OPENAI_COMPATIBLE_MODEL or "default")
    if not model:
        model = OPENAI_COMPATIBLE_MODEL or "default"
    api_key = (runtime.get("api_key") or "").strip() if isinstance(runtime, dict) else OPENAI_COMPATIBLE_API_KEY
    if runtime is None and use_remote:
        use_remote = bool(base)
    elif use_remote and not base:
        use_remote = False

    if use_remote and base:
        max_tok = max_tokens if max_tokens > 0 else 256

        # Optional: Responses API (instructions + input -> output_text)
        if OPENAI_USE_RESPONSES_API and HAS_REQUESTS:
            try:
                instructions = ""
                input_text = ""
                for m in messages:
                    role = (m.get("role") or "").lower()
                    content = (m.get("content") or "").strip()
                    if role == "system":
                        instructions = content if not instructions else f"{instructions}\n\n{content}"
                    elif role == "user":
                        input_text = content
                if not input_text and messages:
                    input_text = (messages[-1].get("content") or "").strip()
                url = f"{base}/responses"
                body = {"model": model, "instructions": instructions or "You are a helpful assistant.", "input": input_text}
                headers = {"Content-Type": "application/json"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                r = requests.post(url, json=body, headers=headers, timeout=120)
                r.raise_for_status()
                data = r.json()
                text = (data.get("output_text") or data.get("output") or "").strip()
                if text:
                    return text
            except Exception as e:
                _log("error", f"Responses API error: {e}, falling back to chat completions")

        # Prefer official OpenAI client when available
        if HAS_OPENAI_CLIENT:
            try:
                client = OpenAI(base_url=base, api_key=api_key or "EMPTY")
                r = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tok,
                    temperature=0,
                )
                text = (r.choices[0].message.content or "").strip()
                return text if text else "DONE"
            except Exception as e:
                _log("error", f"OpenAI client error: {e}")
                if not HAS_REQUESTS:
                    return _fallback_curl_add(base_url) if base_url else "DONE"

        # Fallback: raw HTTP chat/completions
        if HAS_REQUESTS:
            try:
                url = f"{base}/chat/completions"
                body = {"model": model, "messages": messages, "max_tokens": max_tok, "temperature": 0}
                headers = {"Content-Type": "application/json"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                r = requests.post(url, json=body, headers=headers, timeout=120)
                r.raise_for_status()
                data = r.json()
                text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
                return text if text else "DONE"
            except Exception as e:
                _log("error", f"OpenAI-compatible LLM error: {e}")
        return _fallback_curl_add(base_url) if base_url else "DONE"

    if not HAS_OLLAMA:
        return _fallback_curl_add(base_url) if base_url else "DONE"
    try:
        kwargs = {"model": OLLAMA_MODEL, "messages": messages}
        if max_tokens > 0:
            kwargs["options"] = {"num_predict": max_tokens}
        r = ollama.chat(**kwargs)
        text = (r.get("message") or {}).get("content", "").strip()
        return text if text else "DONE"
    except Exception as e:
        err_msg = str(e)
        _log("error", f"Ollama error: {err_msg}")
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


def _extract_json_block(text: str) -> str:
    """Extract JSON object from LLM reply. Supports ```json blocks or raw JSON."""
    if not text:
        return ""
    # ```json\n{...}\n``` or ```\n{...}\n```
    m = re.search(r"```(?:json)?\s*\n(.*?)(?:```|$)", text, re.DOTALL | re.IGNORECASE)
    if m:
        candidate = m.group(1).strip()
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start != -1 and end != -1 and end > start:
            return candidate[start : end + 1]
        return candidate
    # Fallback: first '{' ... last '}' in whole reply
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text.strip()


def _normalize_planner_response(plan: dict) -> dict:
    """Map alternate LLM response shapes (e.g. executions + continuity) to init + continuous schema."""
    if "init" in plan and "continuous" in plan:
        return plan
    out = {}
    init_cmd = None
    if "executions" in plan and isinstance(plan["executions"], list) and plan["executions"]:
        first = plan["executions"][0]
        init_cmd = first.get("command") if isinstance(first, dict) else None
        out["init"] = {
            "enabled": bool(init_cmd),
            "command": init_cmd or "",
            "description": "",
        }
    else:
        out["init"] = plan.get("init") or {"enabled": False, "command": None, "description": ""}
        init_cmd = out["init"].get("command") or ""

    bounds = {}
    if "continuity" in plan and isinstance(plan["continuity"], dict):
        c = plan["continuity"]
        bounds = dict(c.get("bounds") or {})
        out["continuous"] = {
            "mode": c.get("mode") or "loop",
            "interval_seconds": c.get("interval_seconds") or 5,
            "template": c.get("template") or "",
            "parameter_strategy": (c.get("parameter_strategy") or "fixed").lower(),
            "bounds": bounds,
        }
    else:
        out["continuous"] = plan.get("continuous") or {}
        bounds = dict(out["continuous"].get("bounds") or {})

    # Infer max_id from init seed count so continuous transfers use only seeded accounts
    if isinstance(init_cmd, str) and "random_bank_transfers" == out.get("continuous", {}).get("parameter_strategy"):
        m = re.search(r'"count"\s*:\s*(\d+)', init_cmd)
        if m:
            n = int(m.group(1))
            if n >= 1:
                bounds["min_id"] = 1
                bounds["max_id"] = n
                out["continuous"]["bounds"] = bounds
    return out


def _plan_from_llm(manifest: dict, base_url: str, init_goal: str, goal: str) -> dict | None:
    """
    Ask the LLM (ideally llama3.2:3b) to act as a planner and return a small JSON plan.

    Plan schema (conceptual):
    {
      "init": {
        "enabled": true,
        "command": "curl ...",  # single shell command or null/empty
        "description": "optional text"
      },
      "continuous": {
        "mode": "loop",
        "interval_seconds": 5,
        "template": "curl ...",  # may contain {{base_url}} and placeholders
        "parameter_strategy": "fixed" | "random_bank_transfers",
        "bounds": { "min_amount": 5, "max_amount": 100 }
      }
    }
    """
    if not manifest or not (HAS_OLLAMA or USE_OPENAI_COMPATIBLE):
        return None

    system = (
        "You are the planner for DemoForge, a sandbox demo/QA platform.\n"
        "You NEVER execute commands; you ONLY design a small JSON plan that tells an executor\n"
        "what shell commands to run. The executor will enforce run-once vs continuous behavior.\n\n"
        "Rules:\n"
        "- Use ONLY the API endpoints described in the manifest.\n"
        "- Prefer POST /api/seed when seeding many accounts; otherwise use POST /api/accounts and POST /api/transfer.\n"
        "- For init, choose at most ONE shell command (or none). It runs exactly once.\n"
        "- For continuous, design a loop: either a fixed command every few seconds or a command template plus a parameter_strategy.\n"
        "- Reply with a single JSON object, no explanations, no markdown.\n"
        "Output ONLY a single JSON object. No reasoning, no thinking process, no explanation, no markdown except the raw JSON."
    )

    # Trim manifest to essentials so planner prompt stays small (faster inference).
    slim_manifest = {
        "id": manifest.get("id"),
        "description": manifest.get("description"),
        "endpoints": manifest.get("endpoints", []),
        "example_commands": manifest.get("example_commands", [])[:5],
    }
    payload = {
        "manifest": slim_manifest,
        "base_url": base_url,
        "init_goal": init_goal or "",
        "continuous_goal": goal or "",
        "schema": {
            "init": {
                "enabled": "boolean",
                "command": "string | null",
                "description": "string (optional)",
            },
            "continuous": {
                "mode": "\"loop\"",
                "interval_seconds": "number",
                "template": "string",
                "parameter_strategy": "\"fixed\" | \"random_bank_transfers\"",
                "bounds": {
                    "min_amount": "number (optional)",
                    "max_amount": "number (optional)",
                },
            },
        },
        "instructions": (
            "For bank-like manifests with /api/seed and /api/transfer:\n"
            "- If the init goal mentions seeding or creating N users/accounts, set init.enabled=true and init.command to a single curl using /api/seed with count=N if possible.\n"
            "- If the continuous goal mentions transfers or \"between accounts\", set continuous.template to a curl POST /api/transfer with placeholders {{from_id}}, {{to_id}}, {{amount}} "
            "and parameter_strategy=\"random_bank_transfers\" and interval_seconds to around 5.\n"
            "- Otherwise, you may leave init.enabled=false and set a simple continuous.template that fits the goal."
        ),
    }

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload)},
    ]
    _log("info", "Requesting planner JSON plan from LLM.")
    reply = _ask_llm(messages, base_url=base_url, max_tokens=512)
    _log("llm", f"Planner reply: {reply}")

    try:
        raw_json = _extract_json_block(reply)
        plan = json.loads(raw_json)
        if not isinstance(plan, dict):
            raise ValueError("Planner output is not a JSON object")
        # Normalize alternate LLM shapes (e.g. executions + continuity) to init + continuous
        plan = _normalize_planner_response(plan)
        if "init" not in plan or "continuous" not in plan:
            raise ValueError("Planner plan missing init or continuous keys")
        return plan
    except Exception as e:
        _log("error", f"Planner JSON parse failed: {e}")
        return None


def _run_continuous_from_plan(plan: dict, base_url: str) -> bool:
    """
    Run continuous loop using a plan from _plan_from_llm.

    Returns True if a plan-driven loop was started, False if we should fall back to classic LLM loop.
    """
    cont = plan.get("continuous") or {}
    template = cont.get("template")
    if not template:
        return False

    mode = (cont.get("mode") or "loop").lower()
    if mode != "loop":
        return False

    interval = cont.get("interval_seconds") or INTERVAL_SEC
    strategy = (cont.get("parameter_strategy") or "fixed").lower()
    bounds = cont.get("bounds") or {}
    min_amount = bounds.get("min_amount", 5)
    max_amount = bounds.get("max_amount", 100)

    _log("info", f"Using plan-driven continuous loop (strategy={strategy}, interval={interval}s).")

    if strategy == "random_bank_transfers":
        max_id = bounds.get("max_id", 10)
        min_id = bounds.get("min_id", 1)
        if max_id < min_id:
            max_id = min_id
        while _running:
            from_id = random.randint(min_id, max_id)
            to_id = random.randint(min_id, max_id)
            if max_id > min_id:
                while to_id == from_id:
                    to_id = random.randint(min_id, max_id)
            amount = random.randint(int(min_amount), int(max_amount))
            cmd = (
                template.replace("{{base_url}}", base_url)
                .replace("{{from_id}}", str(from_id))
                .replace("{{to_id}}", str(to_id))
                .replace("{{amount}}", str(amount))
            )
            cmd = _strip_trailing_done(cmd)
            _log("command", f"Running (plan/continuous): {cmd}")
            code, stdout, stderr = _run_command(cmd)
            output = f"exit={code}\nstdout:\n{stdout}\nstderr:\n{stderr}"
            _log("output", output[:800])
            time.sleep(interval)
        return True

    fixed_cmd = template.replace("{{base_url}}", base_url)
    while _running:
        cmd = _strip_trailing_done(fixed_cmd)
        _log("command", f"Running (plan/continuous): {cmd}")
        code, stdout, stderr = _run_command(cmd)
        output = f"exit={code}\nstdout:\n{stdout}\nstderr:\n{stderr}"
        _log("output", output[:800])
        time.sleep(interval)
    return True


def _bank_deterministic_loop(base_url: str, n_accounts: int) -> None:
    """
    Deterministic continuous loop for the Bank preset.

    Uses only account IDs in [1..n_accounts] and does not call the LLM at all.
    """
    if n_accounts < 2:
        n_accounts = 2
    # Use a small max amount so we rarely hit "insufficient balance" (accounts start at 100).
    min_amount, max_amount = 1, 20
    _log("info", f"Continuous (bank/deterministic): transfers between accounts 1..{n_accounts} every {INTERVAL_SEC}s.")
    while _running:
        from_id = random.randint(1, n_accounts)
        to_id = random.randint(1, n_accounts)
        if n_accounts > 1:
            while to_id == from_id:
                to_id = random.randint(1, n_accounts)
        amount = random.randint(min_amount, max_amount)
        cmd = (
            f"curl -s -X POST {base_url}/api/transfer "
            f"-H 'Content-Type: application/json' "
            f"-d '{{\"from_id\":{from_id},\"to_id\":{to_id},\"amount\":{amount}}}'"
        )
        cmd = _strip_trailing_done(cmd)
        _log("command", f"Continuous (bank/deterministic): {cmd}")
        code, stdout, stderr = _run_command(cmd)
        output = f"exit={code}\nstdout:\n{stdout}\nstderr:\n{stderr}"
        _log("output", output[:800])
        time.sleep(INTERVAL_SEC)


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
        "- No reasoning or explanation. Output only that one line.\n"
        "- If the goal says 'every N seconds' or 'every N second', output ONLY ONE single command (e.g. one curl POST). The agent will run it, then wait N seconds and ask again. Do NOT output a for-loop or batch of commands for 'every N seconds' goals.\n"
        "- If you are unsure what to do next, output DONE.\n"
        "- Use the minimal set of API calls that match the goal. If the goal is to create (a) single account(s) or run a transfer, use POST /api/accounts once per new account and POST /api/transfer; use POST /api/seed ONLY when the goal explicitly asks to seed or create many users (e.g. 'seed 100 users').\n"
        "- You may combine multiple API calls in one shell command using simple loops or && only when the goal does NOT say 'every N seconds'; e.g. for one-off batch: for i in $(seq 1 5); do curl ...; done\n"
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

    # Deterministic path for Bank preset: no LLM control flow.
    if PRESET == "bank" and not template_id:
        # Parse desired account count N from init_goal; fallback to 3 if not present.
        n_accounts = 3
        if init_goal:
            m = re.search(r"(\d+)", init_goal)
            if m:
                try:
                    n_accounts = max(1, int(m.group(1)))
                except ValueError:
                    n_accounts = 3
        _log("info", f"Init (bank/deterministic): seeding {n_accounts} accounts via /api/seed.")
        seed_cmd = (
            f"curl -s -X POST {base_url}/api/seed "
            f"-H 'Content-Type: application/json' "
            f"-d '{{\"count\":{n_accounts},\"initial_balance\":100,\"name_prefix\":\"User\"}}'"
        )
        code, stdout, stderr = _run_command(seed_cmd)
        output = f"exit={code}\nstdout:\n{stdout}\nstderr:\n{stderr}"
        _log("output", output[:800])
        _log("info", "Init (bank/deterministic) complete, starting continuous loop.")
        _bank_deterministic_loop(base_url, n_accounts)
        return

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
            "- No reasoning or explanation. Output only that one line.\n"
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
            "- Reply with ONLY one line per turn: either a single shell command (e.g. curl ...) or the word DONE. No reasoning or explanation. Output only that one line.\n"
            "- If you are unsure what to do next, output DONE.\n"
            "- You may combine multiple API calls in one shell command using simple loops or &&, e.g.:\n"
            "  for i in $(seq 1 5); do curl ...; done\n"
            "- You may only use shell builtins plus curl and echo. Never use python, rm, apt, brew, or any file-system or package-manager commands.\n"
            "- Do NOT use markdown, backticks, or code fences; output the raw command only."
        )
    messages = [{"role": "system", "content": system}]

    # Planner: one-shot LLM call to get init + continuous plan (when manifest available).
    plan: dict | None = None
    if manifest and manifest.get("endpoints"):
        plan = _plan_from_llm(manifest, base_url, init_goal, goal)

    # Optional init phase: prefer plan's single command; else fall back to LLM init loop.
    if init_goal and not template_id:
        planned_init_cmd = None
        if plan:
            init_cfg = plan.get("init") or {}
            if init_cfg.get("enabled") and init_cfg.get("command"):
                planned_init_cmd = str(init_cfg["command"]).strip()
        if planned_init_cmd:
            cmd = _strip_trailing_done(planned_init_cmd.replace("{{base_url}}", base_url))
            _log("info", f"Running init phase from plan: {cmd}")
            code, stdout, stderr = _run_command(cmd)
            _log("output", f"exit={code}\nstdout:\n{stdout}\nstderr:\n{stderr}"[:800])
            _log("info", "Init phase (plan) complete, switching to main goal.")
        else:
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
                "- Reply with ONLY one line per turn: either a single shell command (e.g. curl ...) or the word DONE. Do NOT append '&& DONE' or '&& echo DONE' to the command. No reasoning or explanation. Output only that one line.\n"
                "- Use the minimal set of API calls that match the goal. For 'create an account and run a transfer' use POST /api/accounts once then POST /api/transfer; use POST /api/seed ONLY when the goal explicitly says to seed or create many users.\n"
                "- You may only use shell builtins plus curl and echo. Do NOT use markdown, backticks, or code fences; output the raw command only."
            )
        else:
            system = (
                f"You are an agent controlling a favorite foods app. The app is at {base_url}.\n"
                f"Goal: {goal}\n\n"
                "To add a food, POST to /add with JSON body {\"food\":\"Pizza\"}.\n"
                "CRITICAL: Reply with ONLY one line: command or DONE. No reasoning or explanation. Output only that one line. Do NOT append && DONE. Do NOT use markdown."
            )
        messages = [{"role": "system", "content": system}]

    # If we have a valid plan with continuous template, run plan-driven loop (no per-step LLM).
    if plan and _run_continuous_from_plan(plan, base_url):
        return

    while _running:
        messages.append({"role": "user", "content": "What single shell command do you run next? (one line: command or DONE; if unsure, output DONE)"})
        _log("info", "Asking LLM for next command...")

        for step in range(MAX_STEPS_PER_ROUND):
            # Limit context to last 8 messages + system to keep prompts small and inference faster.
            trimmed = [messages[0]] + messages[-(2 * 4) :] if len(messages) > 9 else messages
            reply = _ask_llm(trimmed, base_url=base_url, max_tokens=MAX_PREDICT_TOKENS)
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

        wait_sec = _interval_from_goal(goal) or INTERVAL_SEC
        time.sleep(wait_sec)
        messages = [{"role": "system", "content": system}]


if __name__ == "__main__":
    main()
