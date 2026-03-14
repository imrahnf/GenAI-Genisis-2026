# DemoForge vs Hackathon Brief – Analysis

**Brief (target):** *Create a platform for on-demand sandbox environments with production-parity behavior and zero real data. Teams can define reusable demo or QA scenarios that control sandbox contents and enabled features, with a lightweight way to capture walkthroughs and turn them into reusable templates. Each scenario launch produces a fresh, shareable sandbox with synthetic data, role-based access, and lifecycle controls like reset and expiry—all managed through a control panel or API.*

---

## 1. Brief → Codebase Map

| Brief phrase | Where it lives | Status |
|--------------|----------------|--------|
| **On-demand sandbox environments** | `POST /launch` → Docker container + agent per sandbox; URL in seconds | ✅ Done |
| **Production-parity behavior** | Real apps in containers (Flask + SQLite in `sandboxes/preset`, `sandboxes/bank`) | ✅ Done |
| **Zero real data** | Synthetic only (foods, bank accounts/transactions); no PII, no prod DB | ✅ Done |
| **Teams define reusable demo or QA scenarios** | Manifest-driven presets + capture/templates (each template is effectively a reusable scenario) | ✅ Conceptual |
| **Control sandbox contents and enabled features** | `config` (env vars) per launch, now fully manifest-driven via `config_schema` and the config panel | ✅ Done |
| **Lightweight capture of walkthroughs → reusable templates** | `POST /capture/start`, `POST /capture/stop`; `/templates`; agent replay via `DEMOFORGE_TEMPLATE_ID` with URL rewriting | ✅ Done |
| **Fresh, shareable sandbox** | Each launch = new container; URL is shareable (Tailscale IP) | ✅ Done (share link / roles deferred) |
| **Synthetic data** | Preset apps use seed/synthetic data; agent can add more | ✅ Done |
| **Role-based access** | Not implemented (viewer/operator/owner) | ❌ Deferred |
| **Lifecycle: reset and expiry** | `POST /reset/{id}`; `expires_in` → auto-destroy on status poll | ✅ Done |
| **Control panel or API** | Next.js dashboard + full REST API (launch, destroy, status, scenarios, templates, capture) | ✅ Done |

---

## 2. Gaps and Improvements

### Strong vs brief
- On-demand sandboxes, production-parity (real stack), zero real data, scenarios, config, lifecycle (reset + expiry), control panel + API are all there and align with the brief.

### Weak or optional
- **Role-based access:** Out of scope for minimal demo; brief says “role-based access” but many demos ship without it. Can be one slide (“future: viewer/operator/owner”).
- **Shareable:** URL is shareable today; “share link” (e.g. view-only) was explicitly deferred.

### Remove or simplify
- Avoid UI that suggests capture/replay is the main path if it’s flaky; keep it available but secondary (e.g. “Advanced: capture & replay”).
- Single big form is hard to scan; grid of presets + click-for-config is clearer and matches “pick a scenario/preset then configure.”

### Final-setting tweaks
- **UI:** Dashboard = grid of presets; click preset → manifest-driven config panel (goal, config controls, expiry) and Launch. Saved templates / replays section and Active sandboxes table below. Barebones, but focused on the brief’s requirements.
- **API:** `/presets` and `/context/{preset}` expose manifest data so the control panel and agents are always in sync.
- **Docs:** README + use guide + this brief analysis map each bullet of the brief to a concrete feature (manifests, templates, lifecycle, synthetic data).

---

## 3. File Reference

| Area | Files |
|------|--------|
| Orchestrator API | `backend/main.py` |
| Config / presets | `backend/config.py` |
| Agent (LLM + replay) | `backend/agent.py` |
| Agent lifecycle | `backend/agent_manager.py` |
| Preset apps | `sandboxes/preset/`, `sandboxes/bank/` |
| Control panel | `frontend/app/page.tsx`, `frontend/app/globals.css`, `frontend/app/layout.tsx` |
| Vision / brief | `docs/BORDERPASS_VISION.md`, `docs/USE_GUIDE.md` |

---

## 4. Conclusion

The codebase already covers the brief well: on-demand sandboxes, production-parity, zero real data, manifest-driven presets, config, capture/templates, lifecycle (reset + expiry), and control panel + API. The main remaining gap is role-based access, which is explicitly deferred but easy to explain as future work. For the demo, emphasize: (1) manifests as contracts for each sandbox, (2) agents that read those manifests and issue real shell commands, and (3) capture/templates as a lightweight way to turn runs into reusable, deterministic scenarios.
