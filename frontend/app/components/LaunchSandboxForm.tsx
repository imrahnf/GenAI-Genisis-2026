"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronRight, Play } from "lucide-react";
import type { Preset } from "../types";

interface LaunchSandboxFormProps {
  presetName: string;
  preset: Preset | undefined;
  goal: string;
  initGoal: string;
  configState: Record<string, string | number | boolean>;
  configJson: string;
  expiresIn: number | null;
  loading: boolean;
  error: string | null;
  onGoalChange: (v: string) => void;
  onInitGoalChange: (v: string) => void;
  onConfigStateChange: (s: Record<string, string | number | boolean>) => void;
  onConfigJsonChange: (v: string) => void;
  onExpiresInChange: (v: number | null) => void;
  onSubmit: (e: React.FormEvent) => void;
}

export function LaunchSandboxForm({
  presetName,
  preset,
  goal,
  initGoal,
  configState,
  configJson,
  expiresIn,
  loading,
  error,
  onGoalChange,
  onInitGoalChange,
  onConfigStateChange,
  onConfigJsonChange,
  onExpiresInChange,
  onSubmit,
}: LaunchSandboxFormProps) {
  const [settingsOpen, setSettingsOpen] = useState(true);
  const [agentOpen, setAgentOpen] = useState(true);

  const hasConfigSchema = preset?.config_schema && Object.keys(preset.config_schema).length > 0;

  return (
    <div className="flex flex-col gap-10 mt-2 pb-12">
      <div className="flex gap-[45px] items-start">
        <div className="w-[320px] h-[180px] shrink-0 rounded-2xl border-2 border-border bg-secondary overflow-hidden opacity-50 flex items-center justify-center">
          <span className="text-muted-foreground text-sm">Preview pending launch...</span>
        </div>
        <div className="flex flex-col py-2">
          <h2 className="text-[20px] font-normal text-foreground m-0 leading-none mb-4">Launch sandbox</h2>
          <p className="text-[16px] text-muted-foreground leading-none m-0">{presetName}</p>
        </div>
      </div>

      <div className="h-px bg-border w-full" />

      <form onSubmit={onSubmit} className="flex flex-col gap-8 max-w-[800px]">
        {error && (
          <div className="rounded-xl bg-destructive/15 px-4 py-3 text-sm text-destructive">{error}</div>
        )}

        {/* Deployment Settings / Config */}
        <div className="border border-border rounded-2xl bg-secondary/30 overflow-hidden">
          <button
            type="button"
            onClick={() => setSettingsOpen(!settingsOpen)}
            className="w-full flex items-center gap-4 px-5 py-6 hover:bg-secondary/40 transition-colors"
          >
            <span className="text-[18px] font-normal text-foreground">Deployment Settings</span>
            <div className="ml-auto">
              {settingsOpen ? <ChevronDown size={20} className="text-muted-foreground" /> : <ChevronRight size={20} className="text-muted-foreground" />}
            </div>
          </button>
          {settingsOpen && (
            <div className="px-5 pb-6 pt-2 border-t border-border/50">
              {hasConfigSchema && preset ? (
                <div className="grid gap-4 md:grid-cols-2">
                  {Object.entries(preset.config_schema!).map(([key, field]) => {
                    const type = field.type || "text";
                    const label = field.label || key;
                    const value = configState[key];
                    if (type === "boolean") {
                      return (
                        <div className="flex flex-row items-center gap-3 md:col-span-2" key={key}>
                          <label className="min-w-[120px] text-sm text-foreground">{label}</label>
                          <input
                            type="checkbox"
                            checked={Boolean(value)}
                            onChange={(e) => onConfigStateChange({ ...configState, [key]: e.target.checked })}
                            className="h-4 w-4 rounded border-border bg-input-background"
                          />
                          {field.help && <span className="text-xs text-muted-foreground">{field.help}</span>}
                        </div>
                      );
                    }
                    if (type === "select" && field.options?.length) {
                      return (
                        <div className="flex flex-col gap-1.5" key={key}>
                          <label className="text-sm text-foreground">{label}</label>
                          <select
                            value={value !== undefined && value !== null ? String(value) : ""}
                            onChange={(e) => onConfigStateChange({ ...configState, [key]: e.target.value })}
                            className="input-theme"
                          >
                            {field.options.map((opt) => (
                              <option key={String(opt)} value={String(opt)}>{String(opt)}</option>
                            ))}
                          </select>
                          {field.help && <span className="text-xs text-muted-foreground">{field.help}</span>}
                        </div>
                      );
                    }
                    return (
                      <div className="flex flex-col gap-1.5" key={key}>
                        <label className="text-sm text-foreground">{label}</label>
                        <input
                          type={type === "number" ? "number" : "text"}
                          value={value !== undefined && value !== null ? String(value) : ""}
                          onChange={(e) => onConfigStateChange({ ...configState, [key]: type === "number" ? Number(e.target.value) : e.target.value })}
                          className="input-theme"
                        />
                        {field.help && <span className="text-xs text-muted-foreground">{field.help}</span>}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="flex flex-col gap-1.5">
                  <label className="text-sm text-foreground">Config (JSON)</label>
                  <textarea
                    value={configJson}
                    onChange={(e) => onConfigJsonChange(e.target.value)}
                    placeholder="{}"
                    rows={4}
                    className="input-theme font-mono text-xs min-h-[100px] resize-y"
                  />
                </div>
              )}
            </div>
          )}
        </div>

        {/* Agent Settings */}
        <div className="border border-border rounded-2xl bg-secondary/30 overflow-hidden">
          <button
            type="button"
            onClick={() => setAgentOpen(!agentOpen)}
            className="w-full flex items-center gap-4 px-5 py-6 hover:bg-secondary/40 transition-colors"
          >
            <span className="text-[18px] font-normal text-foreground">Agent Settings</span>
            <div className="ml-auto">
              {agentOpen ? <ChevronDown size={20} className="text-muted-foreground" /> : <ChevronRight size={20} className="text-muted-foreground" />}
            </div>
          </button>
          {agentOpen && (
            <div className="px-5 pb-6 pt-2 border-t border-border/50 flex flex-col gap-6">
              <div className="flex flex-col gap-2">
                <label className="text-sm text-foreground">Goal</label>
                <textarea
                  value={goal}
                  onChange={(e) => onGoalChange(e.target.value)}
                  placeholder="e.g. Add a new food every 10 seconds."
                  rows={2}
                  className="input-theme min-h-[80px] resize-y"
                />
                <span className="text-[11px] text-muted-foreground">Runs continuously until the sandbox is destroyed.</span>
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm text-foreground">Init goal (optional)</label>
                <textarea
                  value={initGoal}
                  onChange={(e) => onInitGoalChange(e.target.value)}
                  placeholder="e.g. Seed the database with 50 users"
                  rows={1}
                  className="input-theme"
                />
                <span className="text-[11px] text-muted-foreground">Run once when the container is up, then the agent goal runs continuously.</span>
              </div>
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <label className="text-sm text-foreground">Expires in</label>
            <select
              value={expiresIn ?? ""}
              onChange={(e) => onExpiresInChange(e.target.value === "" ? null : Number(e.target.value))}
              className="input-theme min-w-[140px]"
            >
              <option value="">No expiry</option>
              <option value="60">1 min (demo)</option>
              <option value="300">5 min</option>
              <option value="3600">1 hour</option>
              <option value="7200">2 hours</option>
            </select>
          </div>
          <button type="submit" disabled={loading} className="btn-primary flex items-center gap-2">
            <Play className="h-4 w-4" />
            {loading ? "Launching…" : "Launch sandbox"}
          </button>
        </div>
      </form>
    </div>
  );
}
