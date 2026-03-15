"use client";

import React, { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowLeft, CheckCircle, AlertCircle } from "lucide-react";
import { Sidebar, type Section } from "./components/Sidebar";
import { PresetsSection } from "./components/PresetsSection";
import { LaunchSandboxForm } from "./components/LaunchSandboxForm";
import { ReplaysSection } from "./components/ReplaysSection";
import { SandboxesSection } from "./components/SandboxesSection";
import { LifecycleSection } from "./components/LifecycleSection";
import { LlmSettingsPanel } from "./components/LlmSettingsPanel";
import { type LifecycleEvent } from "./components/LifecycleGraph";
import type { Preset, Sandbox, Template } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

const FALLBACK_GOALS: Record<string, string> = {
  preset: "Add a new food every 10 seconds.",
  bank: "Create an account and run a transfer.",
  spending: "Add transactions; some above the anomaly threshold.",
};

export default function Home() {
  const [activeSection, setActiveSection] = useState<Section>("presets");
  const [presets, setPresets] = useState<Preset[]>([]);
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);
  const [presetSearchQuery, setPresetSearchQuery] = useState("");
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
  const [showLlmSettings, setShowLlmSettings] = useState(false);

  const fetchPresets = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/presets`);
      const data = await r.json();
      setPresets(data.presets || []);
    } catch {
      setPresets([
        { id: "preset", name: "Favorite Foods", description: "Flask app with synthetic food list." },
        { id: "bank", name: "Bank", description: "Mini banking: accounts and transfers." },
      ]);
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
      setConfigJson(base && Object.keys(base).length > 0 ? JSON.stringify(base, null, 2) : "{}");
    }
    setExpiresIn(null);
    setInitGoal("");
  }, [selectedPreset, presets]);

  const handleNavigate = useCallback((section: Section) => {
    setActiveSection(section);
    setSelectedPreset(null);
  }, []);

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
        config = configJson.trim() ? (JSON.parse(configJson) as Record<string, string>) : undefined;
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
      setActiveSection("sandboxes");
      setSelectedPreset(null);
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

  const handleLaunchReplay = async (t: Template) => {
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
          template_id: t.id,
        }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "Replay launch failed");
      setSuccessMessage(`Replay launched from template '${t.name}'.`);
      setTimeout(() => setSuccessMessage(null), 4000);
      await fetchStatus();
      setActiveSection("sandboxes");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Replay launch failed");
    }
  };

  const selectedPresetData = presets.find((x) => x.id === selectedPreset);
  const sectionTitles: Record<Section, string> = {
    presets: "Presets",
    replays: "Replays",
    sandboxes: "Sandboxes",
    lifecycle: "Lifecycle",
  };

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      <Sidebar
        activeSection={activeSection}
        onNavigate={handleNavigate}
        onSettingsClick={() => setShowLlmSettings((v) => !v)}
        sandboxesCount={sandboxes.length}
      />

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <div className="flex-shrink-0 px-8 pt-7 pb-4 border-b border-zinc-800">
          <p className="text-[13px] text-zinc-400 mb-1 font-sans">Overview</p>

          {activeSection === "presets" && selectedPreset ? (
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-4">
                <button
                  type="button"
                  onClick={() => setSelectedPreset(null)}
                  className="p-2 hover:bg-zinc-800 rounded-lg text-zinc-400 hover:text-white transition-colors -ml-2"
                >
                  <ArrowLeft size={18} />
                </button>
                <h1 className="text-zinc-50 m-0 font-sans text-[28px] tracking-tight">
                  Launch sandbox · {selectedPresetData?.name ?? selectedPreset}
                </h1>
              </div>
            </div>
          ) : (
            <h1 className="text-zinc-50 mb-4 font-sans text-[28px] tracking-tight">
              {sectionTitles[activeSection]}
            </h1>
          )}

          {showLlmSettings && (
            <div className="mb-4">
              <LlmSettingsPanel
                useRemote={llmUseRemote}
                base={llmBase}
                model={llmModel}
                apiKey={llmApiKey}
                onUseRemoteChange={(v) => {
                  setLlmUseRemote(v);
                  persistLlmConfig({ use_remote: v });
                }}
                onBaseChange={setLlmBase}
                onModelChange={setLlmModel}
                onApiKeyChange={setLlmApiKey}
                onBlur={() => persistLlmConfig({ base: llmBase, model: llmModel, api_key: llmApiKey })}
              />
            </div>
          )}

          <AnimatePresence mode="wait">
            {error && (
              <motion.div
                key="error"
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="mb-4 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400"
              >
                <AlertCircle size={18} className="flex-shrink-0" />
                {error}
              </motion.div>
            )}
            {successMessage && !error && (
              <motion.div
                key="success"
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="mb-4 flex items-center gap-2 rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-4 py-3 text-sm text-cyan-400"
              >
                <CheckCircle size={18} className="flex-shrink-0" />
                {successMessage}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div className="flex-1 overflow-y-auto px-8 pb-8">
          {activeSection === "presets" && !selectedPreset && (
            <PresetsSection
              presets={presets}
              selectedPreset={selectedPreset}
              onSelectPreset={setSelectedPreset}
              searchQuery={presetSearchQuery}
              onSearchChange={setPresetSearchQuery}
            />
          )}

          {activeSection === "presets" && selectedPreset && (
            <LaunchSandboxForm
              presetName={selectedPresetData?.name ?? selectedPreset}
              preset={selectedPresetData}
              goal={goal}
              initGoal={initGoal}
              configState={configState}
              configJson={configJson}
              expiresIn={expiresIn}
              loading={loading}
              error={error}
              onGoalChange={setGoal}
              onInitGoalChange={setInitGoal}
              onConfigStateChange={setConfigState}
              onConfigJsonChange={setConfigJson}
              onExpiresInChange={setExpiresIn}
              onSubmit={handleLaunch}
            />
          )}

          {activeSection === "replays" && (
            <div className="mt-6">
              <p className="text-[13px] text-muted-foreground mb-4">
                Launch a replay to run a saved walkthrough on a fresh sandbox.
              </p>
              <ReplaysSection templates={templates} onLaunchReplay={handleLaunchReplay} />
            </div>
          )}

          {activeSection === "sandboxes" && (
            <div className="mt-6">
              <p className="text-[13px] text-muted-foreground mb-4">Manage and inspect running sandboxes.</p>
              <SandboxesSection
                sandboxes={sandboxes}
                expandedLogs={expandedLogs}
                captureSaveName={captureSaveName}
                onExpandLogs={setExpandedLogs}
                onCaptureSaveName={setCaptureSaveName}
                onCaptureStart={handleCaptureStart}
                onCaptureStop={handleCaptureStop}
                onReset={handleReset}
                onDestroy={handleDestroy}
              />
            </div>
          )}

          {activeSection === "lifecycle" && (
            <div className="mt-6">
              <LifecycleSection
                events={lifecycleEvents}
                activeSandboxIds={new Set(sandboxes.map((s) => s.sandbox_id))}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
