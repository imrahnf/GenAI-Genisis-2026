"use client";

import React, { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Play, RotateCcw, Trash2, Cpu, Activity, Clock, ExternalLink, Video } from "lucide-react";
import LifecycleGraph, { type LifecycleEvent } from "./components/LifecycleGraph";

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

type ConfigFieldSchema = {
  label?: string;
  type?: "text" | "number" | "boolean" | "select";
  default?: string | number | boolean;
  options?: (string | number)[];
  help?: string;
};

type Preset = {
  id: string;
  name: string;
  description: string;
  synthetic_data?: string;
  capabilities?: string[];
  default_goal?: string;
  default_config?: Record<string, string>;
  config_schema?: Record<string, ConfigFieldSchema>;
};
type Template = { id: string; name: string; preset: string; steps_count: number };

const FALLBACK_GOALS: Record<string, string> = {
  preset: "Add a new food every 10 seconds.",
  bank: "Create an account and run a transfer.",
  spending: "Add transactions; some above the anomaly threshold.",
};

export default function Home() {
  const [presets, setPresets] = useState<Preset[]>([]);
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);
  const [goal, setGoal] = useState("");
  const [configJson, setConfigJson] = useState("{}");
  const [configState, setConfigState] = useState<Record<string, string | number | boolean>>({});
  const [expiresIn, setExpiresIn] = useState<number | null>(null);
  const [initGoal, setInitGoal] = useState("");
  const [sandboxes, setSandboxes] = useState<Sandbox[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [lifecycleEvents, setLifecycleEvents] = useState<LifecycleEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [expandedLogs, setExpandedLogs] = useState<string | null>(null);
  const [captureSaveName, setCaptureSaveName] = useState<{ id: string; name: string } | null>(null);
  const [llmUseRemote, setLlmUseRemote] = useState(false);
  const [llmBase, setLlmBase] = useState("");
  const [llmModel, setLlmModel] = useState("");
  const [llmApiKey, setLlmApiKey] = useState("");

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

  const fetchLifecycleEvents = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/lifecycle-events`);
      const data = await r.json();
      setLifecycleEvents(data.events || []);
    } catch {
      setLifecycleEvents([]);
    }
  }, []);

  const fetchLlmConfig = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/llm-config`);
      const data = await r.json();
      setLlmUseRemote(Boolean(data.use_remote));
      setLlmBase(data.base ?? "");
      setLlmModel(data.model ?? "");
      setLlmApiKey(data.api_key ?? "");
    } catch {
      setLlmUseRemote(false);
      setLlmBase("");
      setLlmModel("");
      setLlmApiKey("");
    }
  }, []);

  const persistLlmConfig = useCallback(
    async (updates: { use_remote?: boolean; base?: string; model?: string; api_key?: string }) => {
      try {
        await fetch(`${API_BASE}/llm-config`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(updates),
        });
      } catch {
        // ignore
      }
    },
    []
  );

  useEffect(() => {
    fetchPresets();
  }, [fetchPresets]);

  useEffect(() => {
    fetchLlmConfig();
  }, [fetchLlmConfig]);

  useEffect(() => {
    fetchStatus();
    const t = setInterval(fetchStatus, 4000);
    return () => clearInterval(t);
  }, [fetchStatus]);

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  useEffect(() => {
    fetchLifecycleEvents();
    const t = setInterval(fetchLifecycleEvents, 4000);
    return () => clearInterval(t);
  }, [fetchLifecycleEvents]);

  useEffect(() => {
    if (!selectedPreset) return;
    const p = presets.find((x) => x.id === selectedPreset);
    setGoal(p?.default_goal ?? FALLBACK_GOALS[selectedPreset] ?? "");
    if (p?.config_schema && Object.keys(p.config_schema).length > 0) {
      const initial: Record<string, string | number | boolean> = {};
      for (const [key, field] of Object.entries(p.config_schema)) {
        if (p.default_config && key in p.default_config) {
          initial[key] = p.default_config[key] as string;
        } else if (field.default !== undefined) {
          initial[key] = field.default;
        }
      }
      setConfigState(initial);
      setConfigJson(JSON.stringify(initial, null, 2));
    } else {
      const base = p?.default_config ?? {};
      setConfigState(base);
      setConfigJson(
        base && Object.keys(base).length > 0
          ? JSON.stringify(base, null, 2)
          : "{}"
      );
    }
    setExpiresIn(null);
    setInitGoal("");
  }, [selectedPreset, presets]);

  const handleLaunch = async (e: React.FormEvent) => {
    e.preventDefault();
    const preset = selectedPreset || "preset";
    setLoading(true);
    setError(null);
    const p = presets.find((x) => x.id === preset);
    let config: Record<string, string> | undefined;
    if (p?.config_schema && Object.keys(p.config_schema).length > 0) {
      const cfg: Record<string, string> = {};
      for (const key of Object.keys(p.config_schema)) {
        const val = configState[key];
        const def = p.config_schema[key]?.default;
        const out = val !== undefined && val !== null && val !== "" ? val : def;
        if (out !== undefined && out !== null && out !== "") {
          cfg[key] = String(out);
        }
      }
      config = Object.keys(cfg).length > 0 ? cfg : undefined;
    } else {
      try {
        config = configJson.trim() ? JSON.parse(configJson) as Record<string, string> : undefined;
      } catch {
        setError("Invalid JSON in config");
        setLoading(false);
        return;
      }
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
          init_goal: initGoal.trim() || undefined,
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
    <main className="min-h-screen pb-12">
      <header className="sticky top-0 z-20 -mx-4 -mt-4 mb-6 rounded-2xl border border-stone-200/80 bg-white/90 px-6 py-4 shadow-card backdrop-blur-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-lg font-semibold tracking-tight text-stone-900">DemoForge</h1>
            <p className="mt-0.5 text-sm text-stone-500">On-demand sandboxes · Templates · Lifecycle controls</p>
          </div>
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-stone-600">LLM</span>
              <button
                type="button"
                role="switch"
                aria-checked={llmUseRemote}
                onClick={() => {
                  const v = !llmUseRemote;
                  setLlmUseRemote(v);
                  persistLlmConfig({ use_remote: v });
                }}
                className="relative inline-flex h-8 w-[11rem] flex-shrink-0 rounded-full border border-stone-200 bg-stone-100 transition-colors focus:outline-none focus:ring-2 focus:ring-stone-900/20"
              >
                <span
                  className={`pointer-events-none absolute inset-y-1 flex h-6 w-[5.25rem] items-center justify-center rounded-full text-xs font-medium transition-all ${
                    llmUseRemote ? "left-[calc(100%-5.5rem)] bg-stone-900 text-white" : "left-1 bg-white text-stone-700 shadow-sm"
                  }`}
                >
                  {llmUseRemote ? "Remote" : "IBM Watson"}
                </span>
              </button>
            </div>
            <motion.div
              initial={false}
              animate={{ opacity: llmUseRemote ? 1 : 0, height: llmUseRemote ? "auto" : 0 }}
              transition={{ duration: 0.2 }}
              className={`flex flex-wrap items-end gap-3 overflow-hidden ${llmUseRemote ? "visible" : "invisible pointer-events-none"}`}
            >
              <div className="flex flex-col gap-1">
                <label className="text-[10px] font-medium uppercase tracking-wider text-stone-500">Base URL</label>
                <input
                  type="text"
                  placeholder="http://localhost:8000/v1"
                  value={llmBase}
                  onChange={(e) => setLlmBase(e.target.value)}
                  onBlur={() => persistLlmConfig({ base: llmBase, model: llmModel, api_key: llmApiKey })}
                  className="input-wealthsimple min-w-[200px]"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[10px] font-medium uppercase tracking-wider text-stone-500">Model</label>
                <input
                  type="text"
                  placeholder="openai/gpt-oss-20b"
                  value={llmModel}
                  onChange={(e) => setLlmModel(e.target.value)}
                  onBlur={() => persistLlmConfig({ base: llmBase, model: llmModel, api_key: llmApiKey })}
                  className="input-wealthsimple min-w-[140px]"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[10px] font-medium uppercase tracking-wider text-stone-500">API key</label>
                <input
                  type="password"
                  placeholder="Optional"
                  value={llmApiKey}
                  onChange={(e) => setLlmApiKey(e.target.value)}
                  onBlur={() => persistLlmConfig({ base: llmBase, model: llmModel, api_key: llmApiKey })}
                  className="input-wealthsimple min-w-[100px]"
                />
              </div>
            </motion.div>
          </div>
        </div>
      </header>

      <section className="mb-8">
        <h2 className="mb-3 text-sm font-semibold text-stone-900">Presets</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {presets.map((p) => (
            <motion.button
              key={p.id}
              type="button"
              whileHover={{ y: -2 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => setSelectedPreset(selectedPreset === p.id ? null : p.id)}
              className={`flex flex-col gap-2 rounded-2xl border px-6 py-5 text-left shadow-card transition-shadow ${
                selectedPreset === p.id
                  ? "border-stone-900/30 bg-white ring-1 ring-stone-900/10"
                  : "border-stone-200/60 bg-white hover:shadow-cardHover"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-stone-900">{p.name}</span>
                {selectedPreset === p.id && <Activity className="h-4 w-4 text-stone-500" />}
              </div>
              <div className="flex flex-wrap gap-1.5">
                <span className="rounded-full bg-stone-100 px-2 py-0.5 text-[10px] font-medium text-stone-600">Flask · SQLite</span>
                {p.synthetic_data && <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-stone-600">Synthetic data</span>}
              </div>
              <span className="text-xs leading-snug text-stone-600">{p.description}</span>
            </motion.button>
          ))}
        </div>
      </section>

      <AnimatePresence>
        {selectedPreset && (() => {
          const p = presets.find((x) => x.id === selectedPreset);
          return (
            <motion.section
              key={selectedPreset}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="mb-8 rounded-3xl border border-stone-200 bg-white px-6 py-5 shadow-card"
            >
              <h2 className="text-sm font-semibold text-stone-900">Launch sandbox · {p?.name ?? selectedPreset}</h2>
              {(p?.capabilities?.length || p?.synthetic_data) ? (
                <div className="mt-3 space-y-1 border-b border-stone-100 pb-4">
                  {p.synthetic_data && <p className="text-xs text-stone-500"><span className="font-medium text-stone-600">Synthetic data:</span> {p.synthetic_data}</p>}
                  {p.capabilities && p.capabilities.length > 0 && (
                    <p className="text-xs text-stone-500"><span className="font-medium text-stone-600">Capabilities:</span> {p.capabilities.join(" · ")}</p>
                  )}
                </div>
              ) : null}
              <form onSubmit={handleLaunch} className="mt-4 flex flex-col gap-4">
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-medium text-stone-700">Agent goal</label>
                  <textarea
                    value={goal}
                    onChange={(e) => setGoal(e.target.value)}
                    placeholder="e.g. Add a new food every 10 seconds."
                    rows={2}
                    className="input-wealthsimple min-h-[60px] resize-y"
                  />
                  <span className="text-[11px] text-stone-500">Runs continuously until the sandbox is destroyed.</span>
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-medium text-stone-700">Init goal (optional)</label>
                  <textarea
                    value={initGoal}
                    onChange={(e) => setInitGoal(e.target.value)}
                    placeholder="e.g. Seed the database with 50 users"
                    rows={1}
                    className="input-wealthsimple"
                  />
                  <span className="text-[11px] text-stone-500">Run once when the container is up, then the agent goal runs continuously.</span>
                </div>
                {p?.config_schema && Object.keys(p.config_schema).length > 0 ? (
                  <div className="grid gap-4 md:grid-cols-2">
                    {Object.entries(p.config_schema).map(([key, field]) => {
                      const type = field.type || "text";
                      const label = field.label || key;
                      const value = configState[key];
                      if (type === "boolean") {
                        return (
                          <div className="flex flex-row items-center gap-3 md:col-span-2" key={key}>
                            <label className="min-w-[120px] text-xs font-medium text-stone-700">{label}</label>
                            <input
                              type="checkbox"
                              checked={Boolean(value)}
                              onChange={(e) => setConfigState({ ...configState, [key]: e.target.checked })}
                              className="h-4 w-4 rounded border-stone-300"
                            />
                            {field.help && <span className="text-[11px] text-stone-500">{field.help}</span>}
                          </div>
                        );
                      }
                      if (type === "select" && field.options && field.options.length > 0) {
                        return (
                          <div className="flex flex-col gap-1.5" key={key}>
                            <label className="text-xs font-medium text-stone-700">{label}</label>
                            <select
                              value={value !== undefined && value !== null ? String(value) : ""}
                              onChange={(e) => setConfigState({ ...configState, [key]: e.target.value })}
                              className="input-wealthsimple"
                            >
                              {field.options.map((opt) => (
                                <option key={String(opt)} value={String(opt)}>{String(opt)}</option>
                              ))}
                            </select>
                            {field.help && <span className="text-[11px] text-stone-500">{field.help}</span>}
                          </div>
                        );
                      }
                      return (
                        <div className="flex flex-col gap-1.5" key={key}>
                          <label className="text-xs font-medium text-stone-700">{label}</label>
                          <input
                            type={type === "number" ? "number" : "text"}
                            value={value !== undefined && value !== null ? String(value) : ""}
                            onChange={(e) => setConfigState({ ...configState, [key]: type === "number" ? Number(e.target.value) : e.target.value })}
                            className="input-wealthsimple"
                          />
                          {field.help && <span className="text-[11px] text-stone-500">{field.help}</span>}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="flex flex-col gap-1.5">
                    <label className="text-xs font-medium text-stone-700">Config (JSON env)</label>
                    <textarea value={configJson} onChange={(e) => setConfigJson(e.target.value)} placeholder="{}" rows={2} className="input-wealthsimple font-mono text-xs" />
                  </div>
                )}
                <div className="flex flex-row flex-wrap items-center gap-4 border-t border-stone-100 pt-4">
                  <div className="flex items-center gap-2">
                    <label className="text-xs font-medium text-stone-700">Expires in</label>
                    <select
                      value={expiresIn ?? ""}
                      onChange={(e) => setExpiresIn(e.target.value === "" ? null : Number(e.target.value))}
                      className="input-wealthsimple min-w-[120px]"
                    >
                      <option value="">No expiry</option>
                      <option value="60">1 min (demo)</option>
                      <option value="300">5 min</option>
                      <option value="3600">1 hour</option>
                      <option value="7200">2 hours</option>
                    </select>
                  </div>
                  <button type="submit" disabled={loading} className="btn-primary">
                    <Play className="h-4 w-4" />
                    {loading ? "Launching…" : "Launch sandbox"}
                  </button>
                </div>
              </form>
            </motion.section>
          );
        })()}
      </AnimatePresence>

      <section className="mb-8">
        <h2 className="mb-1 text-sm font-semibold text-stone-900">Saved templates / replays</h2>
        <p className="mb-4 text-xs text-stone-500">Launch a replay to run a saved walkthrough on a fresh sandbox.</p>
        <div className="rounded-3xl border border-stone-200 bg-white px-6 py-4 shadow-card">
          {templates.length === 0 ? (
            <p className="py-4 text-sm text-stone-500">No templates yet. Start a sandbox, click Capture, then Stop &amp; save.</p>
          ) : (
            <div className="divide-y divide-stone-100">
              {templates.map((t) => (
                <div key={t.id} className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-stone-900">{t.name}</span>
                    <span className="rounded-full bg-stone-100 px-2 py-0.5 text-[10px] text-stone-600">{t.preset}</span>
                    <span className="text-xs text-stone-500">{t.steps_count} steps</span>
                  </div>
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
                    className="btn-ghost inline-flex items-center gap-1.5 rounded-full bg-stone-100 px-3 py-2 text-xs font-medium hover:bg-stone-200"
                  >
                    <Play className="h-3.5 w-3.5" />
                    Launch replay
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {error && <p className="mb-4 rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}
      {successMessage && <p className="mb-4 rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{successMessage}</p>}

      <section className="mb-8">
        <h2 className="mb-1 text-sm font-semibold text-stone-900">Lifecycle</h2>
        <p className="mb-4 text-xs text-stone-500">Event flow: launches (green), recording (red), replays (blue), destroyed (×).</p>
        {lifecycleEvents.length === 0 ? (
          <p className="rounded-2xl border border-stone-200 bg-stone-50/50 px-6 py-12 text-center text-sm text-stone-500">
            No events yet. Launch a sandbox to see the lifecycle graph.
          </p>
        ) : (
          <LifecycleGraph
            events={lifecycleEvents}
            activeSandboxIds={new Set(sandboxes.map((s) => s.sandbox_id))}
          />
        )}
      </section>

      <section>
        <h2 className="mb-1 text-sm font-semibold text-stone-900">Active sandboxes</h2>
        <p className="mb-4 text-xs text-stone-500">Manage and inspect running sandboxes.</p>
        {sandboxes.length === 0 ? (
          <p className="rounded-3xl border border-stone-200 bg-white px-6 py-8 text-center text-sm text-stone-500 shadow-card">No sandboxes. Select a preset and launch above.</p>
        ) : (
          <div className="rounded-3xl border border-stone-200 bg-white shadow-card overflow-hidden">
            {sandboxes.map((s) => (
              <React.Fragment key={s.sandbox_id}>
                <div className="grid grid-cols-1 gap-2 border-b border-stone-100 px-6 py-4 last:border-b-0 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_minmax(0,1.2fr)_auto] md:items-center">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-stone-900">{s.preset ?? "preset"}</span>
                    {s.template_id && <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-stone-600">Replay</span>}
                  </div>
                  <a href={s.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs text-stone-600 hover:text-stone-900">
                    {s.url}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                  <p className="truncate text-xs text-stone-500" title={s.goal}>{s.goal}</p>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`rounded-full px-2 py-0.5 text-[10px] ${formatExpires(s.expires_at) === "expired" ? "bg-rose-50 text-rose-600" : "bg-stone-100 text-stone-600"}`}>
                      {formatExpires(s.expires_at) === "expired" ? "Expired" : formatExpires(s.expires_at)}
                    </span>
                    <button type="button" onClick={() => setExpandedLogs(expandedLogs === s.sandbox_id ? null : s.sandbox_id)} className="btn-ghost text-xs">
                      Logs{s.logs?.length ? ` (${s.logs.length})` : ""}
                    </button>
                    {s.capture_active ? (
                      <>
                        <span className="text-[10px] text-stone-500">Recording ({s.capture_steps_count ?? 0})</span>
                        <button type="button" onClick={() => setCaptureSaveName({ id: s.sandbox_id, name: "" })} className="btn-ghost inline-flex items-center gap-1 text-xs">
                          <Video className="h-3.5 w-3.5" />
                          Stop & save
                        </button>
                        {captureSaveName?.id === s.sandbox_id && (
                          <span className="flex items-center gap-2">
                            <input
                              type="text"
                              placeholder="Template name"
                              value={captureSaveName.name}
                              onChange={(e) => setCaptureSaveName({ ...captureSaveName!, name: e.target.value })}
                              className="input-wealthsimple w-28 text-xs"
                            />
                            <button type="button" onClick={() => handleCaptureStop(s.sandbox_id, true, captureSaveName.name)} className="btn-ghost text-xs">Save</button>
                            <button type="button" onClick={() => handleCaptureStop(s.sandbox_id, false, "")} className="btn-ghost text-xs">Cancel</button>
                          </span>
                        )}
                      </>
                    ) : (
                      <button type="button" onClick={() => handleCaptureStart(s.sandbox_id)} className="btn-ghost inline-flex items-center gap-1 rounded-full bg-emerald-50 px-3 py-2 text-xs text-stone-700 hover:bg-emerald-100">
                        <Video className="h-3.5 w-3.5" />
                        Capture
                      </button>
                    )}
                    <button type="button" onClick={() => handleReset(s.sandbox_id)} className="btn-ghost inline-flex items-center gap-1 text-xs">
                      <RotateCcw className="h-3.5 w-3.5" />
                      Reset
                    </button>
                    <button type="button" onClick={() => handleDestroy(s.sandbox_id)} className="btn-destroy inline-flex items-center gap-1 text-xs">
                      <Trash2 className="h-3.5 w-3.5" />
                      Destroy
                    </button>
                  </div>
                </div>
                {expandedLogs === s.sandbox_id && (
                  <div className="border-t border-stone-100 bg-stone-50 px-6 py-3">
                    <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-stone-500">Agent logs</p>
                    <pre className="max-h-56 overflow-auto rounded-2xl bg-stone-100 px-3 py-2 font-mono text-[11px] text-stone-700 whitespace-pre-wrap break-all">
                      {(!s.logs || s.logs.length === 0) ? "No logs." : s.logs.map((l) => `${new Date(l.ts * 1000).toISOString().slice(11, 19)} [${l.type}] ${l.message}`).join("\n")}
                    </pre>
                  </div>
                )}
              </React.Fragment>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
