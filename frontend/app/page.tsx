"use client";

import React, { useState, useEffect, useCallback } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

type LogEntry = { ts: number; type: string; message: string };
type Sandbox = {
  sandbox_id: string;
  url: string;
  port: number;
  goal: string;
  preset?: string;
  template_id?: string | null;
  expires_at?: number | null;
  capture_active?: boolean;
  capture_steps_count?: number;
  logs?: LogEntry[];
};
type Preset = { id: string; name: string; description: string };
type Template = { id: string; name: string; preset: string; steps_count: number };

const DEFAULT_GOALS: Record<string, string> = {
  preset: "Add a new food every 10 seconds.",
  bank: "Create an account and run a transfer.",
};

export default function Home() {
  const [presets, setPresets] = useState<Preset[]>([]);
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);
  const [goal, setGoal] = useState("");
  const [configJson, setConfigJson] = useState("{}");
  const [expiresIn, setExpiresIn] = useState<number | null>(null);
  const [sandboxes, setSandboxes] = useState<Sandbox[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [expandedLogs, setExpandedLogs] = useState<string | null>(null);
  const [captureSaveName, setCaptureSaveName] = useState<{ id: string; name: string } | null>(null);

  const fetchPresets = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/presets`);
      const data = await r.json();
      setPresets(data.presets || []);
    } catch {
      setPresets([{ id: "preset", name: "Favorite Foods", description: "Flask app with synthetic food list." }, { id: "bank", name: "Bank", description: "Mini banking: accounts and transfers." }]);
    }
  }, []);

  const fetchStatus = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/status`);
      const data = await r.json();
      setSandboxes(data.sandboxes || []);
    } catch {
      setSandboxes([]);
    }
  }, []);

  const fetchTemplates = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/templates`);
      const data = await r.json();
      setTemplates(data.templates || []);
    } catch {
      setTemplates([]);
    }
  }, []);

  useEffect(() => {
    fetchPresets();
  }, [fetchPresets]);

  useEffect(() => {
    fetchStatus();
    const t = setInterval(fetchStatus, 4000);
    return () => clearInterval(t);
  }, [fetchStatus]);

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  useEffect(() => {
    if (selectedPreset && !goal) setGoal(DEFAULT_GOALS[selectedPreset] ?? "");
  }, [selectedPreset, goal]);

  const handleLaunch = async (e: React.FormEvent) => {
    e.preventDefault();
    const preset = selectedPreset || "preset";
    setLoading(true);
    setError(null);
    let config: Record<string, string> | undefined;
    try {
      config = configJson.trim() ? JSON.parse(configJson) : undefined;
    } catch {
      setError("Invalid JSON in config");
      setLoading(false);
      return;
    }
    try {
      const r = await fetch(`${API_BASE}/launch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          preset,
          goal,
          config,
          expires_in: expiresIn ?? undefined,
        }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "Launch failed");
      setSuccessMessage("Sandbox launched.");
      setTimeout(() => setSuccessMessage(null), 3000);
      await fetchStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Launch failed");
    } finally {
      setLoading(false);
    }
  };

  const handleDestroy = async (sandboxId: string) => {
    try {
      await fetch(`${API_BASE}/destroy/${sandboxId}`, { method: "POST" });
      await fetchStatus();
    } catch {
      await fetchStatus();
    }
  };

  const handleReset = async (sandboxId: string) => {
    try {
      const r = await fetch(`${API_BASE}/reset/${sandboxId}`, { method: "POST" });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail);
      await fetchStatus();
    } catch {
      await fetchStatus();
    }
  };

  const handleCaptureStart = async (sandboxId: string) => {
    try {
      await fetch(`${API_BASE}/capture/start/${sandboxId}`, { method: "POST" });
      await fetchStatus();
    } catch {
      await fetchStatus();
    }
  };

  const handleCaptureStop = async (sandboxId: string, saveAsTemplate: boolean, name: string) => {
    try {
      const r = await fetch(`${API_BASE}/capture/stop/${sandboxId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ save_as_template: saveAsTemplate, name: name || "Unnamed template" }),
      });
      const data = await r.json();
      setCaptureSaveName(null);
      if (data.message) {
        setSuccessMessage(data.message);
        setTimeout(() => setSuccessMessage(null), 6000);
      }
      await fetchStatus();
      if (saveAsTemplate) await fetchTemplates();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Capture stop failed");
      await fetchStatus();
      setCaptureSaveName(null);
    }
  };

  function formatExpires(expiresAt: number | string | null | undefined) {
    if (expiresAt == null || expiresAt === "") return "—";
    const t = typeof expiresAt === "string" ? parseFloat(expiresAt) : expiresAt;
    if (Number.isNaN(t)) return "—";
    const d = new Date(t * 1000);
    const now = Date.now();
    if (d.getTime() <= now) return "expired";
    const minLeft = Math.round((d.getTime() - now) / 60000);
    return `${d.toLocaleTimeString()} (in ${minLeft} min)`;
  }

  return (
    <main className="dashboard">
      <header className="dashboard-header">
        <h1>DemoForge</h1>
        <p className="tagline">On-demand sandboxes · Templates · Lifecycle controls</p>
      </header>

      <section className="preset-grid">
        <h2>Presets</h2>
        <div className="preset-cards">
          {presets.map((p) => (
            <button
              key={p.id}
              type="button"
              className={`preset-card ${selectedPreset === p.id ? "selected" : ""}`}
              onClick={() => setSelectedPreset(selectedPreset === p.id ? null : p.id)}
            >
              <span className="preset-name">{p.name}</span>
              <span className="preset-desc">{p.description}</span>
            </button>
          ))}
        </div>
      </section>

      {selectedPreset && (
        <section className="config-panel">
          <h2>Launch sandbox · {presets.find((p) => p.id === selectedPreset)?.name ?? selectedPreset}</h2>
          <form onSubmit={handleLaunch} className="config-form">
            <div className="field">
              <label>Agent goal</label>
              <textarea value={goal} onChange={(e) => setGoal(e.target.value)} placeholder="e.g. Add a new food every 10 seconds." rows={2} />
            </div>
            <div className="field">
              <label>Config (JSON env)</label>
              <textarea value={configJson} onChange={(e) => setConfigJson(e.target.value)} placeholder="{}" rows={1} />
            </div>
            <div className="field row">
              <label>Expires in</label>
              <select value={expiresIn ?? ""} onChange={(e) => setExpiresIn(e.target.value === "" ? null : Number(e.target.value))}>
                <option value="">No expiry</option>
                <option value="300">5 min</option>
                <option value="3600">1 hour</option>
                <option value="7200">2 hours</option>
              </select>
            </div>
            <button type="submit" disabled={loading}>{loading ? "Launching…" : "Launch sandbox"}</button>
          </form>
        </section>
      )}

      <section className="templates-section">
        <h2>Saved templates / replays</h2>
        <p className="hint">Each template is a saved walkthrough (commands). Launch a replay to run it again on a fresh sandbox.</p>
        {templates.length === 0 ? (
          <p className="empty">No templates yet. Start a sandbox, click Capture, then Stop &amp; save.</p>
        ) : (
          <table className="sandboxes-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Preset</th>
                <th>Steps</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {templates.map((t) => (
                <tr key={t.id}>
                  <td>{t.name}</td>
                  <td>{t.preset}</td>
                  <td>{t.steps_count}</td>
                  <td>
                    <button
                      type="button"
                      onClick={async () => {
                        setError(null);
                        setSuccessMessage(null);
                        try {
                          const r = await fetch(`${API_BASE}/launch`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({
                              preset: t.preset,
                              goal: `Replay template ${t.name}`,
                              config: {},
                              expires_in: expiresIn ?? undefined,
                              template_id: t.id,
                            }),
                          });
                          const data = await r.json();
                          if (!r.ok) throw new Error(data.detail || "Replay launch failed");
                          setSuccessMessage(`Replay launched from template '${t.name}'.`);
                          setTimeout(() => setSuccessMessage(null), 4000);
                          await fetchStatus();
                        } catch (e) {
                          setError(e instanceof Error ? e.message : "Replay launch failed");
                        }
                      }}
                    >
                      Launch replay
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {error && <p className="message error">{error}</p>}
      {successMessage && <p className="message success">{successMessage}</p>}

      <section className="sandboxes-section">
        <h2>Active sandboxes</h2>
        {sandboxes.length === 0 ? (
          <p className="empty">No sandboxes. Select a preset and launch above.</p>
        ) : (
          <table className="sandboxes-table">
            <thead>
              <tr>
                <th>Preset</th>
                <th>URL</th>
                <th>Goal</th>
                <th>Expires</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sandboxes.map((s) => (
                <React.Fragment key={s.sandbox_id}>
                  <tr>
                    <td>{s.preset ?? "preset"}{s.template_id && <span className="badge">Replay</span>}</td>
                    <td><a href={s.url} target="_blank" rel="noopener noreferrer">{s.url}</a></td>
                    <td className="goal-cell">{s.goal}</td>
                    <td>{formatExpires(s.expires_at)}</td>
                    <td className="actions">
                      <button type="button" onClick={() => setExpandedLogs(expandedLogs === s.sandbox_id ? null : s.sandbox_id)}>Logs{s.logs?.length ? ` (${s.logs.length})` : ""}</button>
                      {s.capture_active ? (
                        <>
                          <span className="muted">Recording ({s.capture_steps_count ?? 0})</span>
                          <button type="button" onClick={() => setCaptureSaveName({ id: s.sandbox_id, name: "" })}>Stop & save</button>
                          {captureSaveName?.id === s.sandbox_id && (
                            <span>
                              <input type="text" placeholder="Template name" value={captureSaveName.name} onChange={(e) => setCaptureSaveName({ ...captureSaveName!, name: e.target.value })} />
                              <button type="button" onClick={() => handleCaptureStop(s.sandbox_id, true, captureSaveName.name)}>Save</button>
                              <button type="button" onClick={() => handleCaptureStop(s.sandbox_id, false, "")}>Cancel</button>
                            </span>
                          )}
                        </>
                      ) : (
                        <button type="button" onClick={() => handleCaptureStart(s.sandbox_id)}>Capture</button>
                      )}
                      <button type="button" onClick={() => handleReset(s.sandbox_id)}>Reset</button>
                      <button type="button" className="danger" onClick={() => handleDestroy(s.sandbox_id)}>Destroy</button>
                    </td>
                  </tr>
                  {expandedLogs === s.sandbox_id && (
                    <tr>
                      <td colSpan={5} className="logs-cell">
                        <pre>{(!s.logs || s.logs.length === 0) ? "No logs." : s.logs.map((l, i) => `${new Date(l.ts * 1000).toISOString().slice(11, 19)} [${l.type}] ${l.message}`).join("\n")}</pre>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}
