# DemoForge vs Hackathon Brief – Analysis

**Brief (target):** *Create a platform for on-demand sandbox environments with production-parity behavior and zero real data. Teams can define reusable demo or QA scenarios that control sandbox contents and enabled features, with a lightweight way to capture walkthroughs and turn them into reusable templates. Each scenario launch produces a fresh, shareable sandbox with synthetic data, role-based access, and lifecycle controls like reset and expiry—all managed through a control panel or API.*

---

## 1. Brief → Codebase Map

| Brief phrase | Where it lives | Status |
|--------------|----------------|--------|
| **On-demand sandbox environments** | `POST /launch` → Docker container + agent per sandbox; URL in seconds | ✅ Done |
| **Production-parity behavior** | Real apps in containers (Flask + SQLite in `sandboxes/preset`, `sandboxes/bank`) | ✅ Done |
| **Zero real data** | Synthetic only (foods, bank accounts/transactions); no PII, no prod DB | ✅ Done |
| **Teams define reusable demo or QA scenarios** | `GET/POST/PUT/DELETE /scenarios`; scenario = name + preset + default_goal + default_config + template_id | ✅ Done |
| **Control sandbox contents and enabled features** | `config` (env vars) per launch; scenarios can set default_config | ✅ Done |
| **Lightweight capture of walkthroughs → reusable templates** | `POST /capture/start`, `POST /capture/stop`; `GET/POST /templates`; agent replay via `DEMOFORGE_TEMPLATE_ID` | ⚠️ Implemented but flaky (capture/replay) |
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
- **Capture/templates:** Implemented end-to-end but brittle (agent log delivery, template fetch). For a “final” demo, either fix replay reliability or simplify to “scenario with fixed action list” and keep capture as a future enhancement.
- **Role-based access:** Out of scope for minimal demo; brief says “role-based access” but many demos ship without it. Can be one slide (“future: viewer/operator/owner”).
- **Shareable:** URL is shareable today; “share link” (e.g. view-only) was explicitly deferred.

### Remove or simplify
- Avoid UI that suggests capture/replay is the main path if it’s flaky; keep it available but secondary (e.g. “Advanced: capture & replay”).
- Single big form is hard to scan; grid of presets + click-for-config is clearer and matches “pick a scenario/preset then configure.”

### Final-setting tweaks
- **UI:** Dashboard = grid of presets; click preset → show config (goal, config JSON, expiry, scenario, template) and Launch. Scenarios as a compact “Reusable scenarios” section (create, list, use in launch). Active sandboxes table below. Barebones, no heavy UI investment.
- **API:** Add `GET /presets` returning id, name, description so the control panel can drive the grid from API (optional; can hardcode in frontend for now).
- **Docs:** One-pager or README section that maps each bullet of the brief to a feature (this doc is the source).

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

The codebase already covers the brief well: on-demand sandboxes, production-parity, zero real data, reusable scenarios, config, lifecycle (reset + expiry), and control panel + API. The main gaps are (1) capture/templates being flaky, and (2) role-based access deferred. For a “perfect, final” demo: simplify the UI to a preset grid + config panel, keep scenarios and lifecycle prominent, and treat capture/replay as an advanced or future feature unless you fix replay reliability.
