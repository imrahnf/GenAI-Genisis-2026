"use client";

import React from "react";

interface LlmSettingsPanelProps {
  useRemote: boolean;
  base: string;
  model: string;
  apiKey: string;
  onUseRemoteChange: (v: boolean) => void;
  onBaseChange: (v: string) => void;
  onModelChange: (v: string) => void;
  onApiKeyChange: (v: string) => void;
  onBlur: () => void;
}

export function LlmSettingsPanel({
  useRemote,
  base,
  model,
  apiKey,
  onUseRemoteChange,
  onBaseChange,
  onModelChange,
  onApiKeyChange,
  onBlur,
}: LlmSettingsPanelProps) {
  return (
    <div className="flex flex-col gap-4 p-4 rounded-2xl border border-border bg-card max-w-lg">
      <p className="text-[13px] text-muted-foreground">LLM backend used by agents for commands and planning.</p>
      <div className="flex items-center gap-3">
        <span className="text-xs font-medium text-foreground">Provider</span>
        <button
          type="button"
          role="switch"
          aria-checked={useRemote}
          onClick={() => onUseRemoteChange(!useRemote)}
          className="relative inline-flex h-8 w-[11rem] flex-shrink-0 rounded-full border border-border bg-secondary transition-colors focus:outline-none focus:ring-2 focus:ring-accent/30"
        >
          <span
            className={`pointer-events-none absolute inset-y-1 flex h-6 w-[5.25rem] items-center justify-center rounded-full text-xs font-medium transition-all ${
              useRemote ? "left-[calc(100%-5.5rem)] bg-accent text-accent-foreground" : "left-1 bg-card text-foreground border border-border"
            }`}
          >
            {useRemote ? "Remote" : "IBM Watson"}
          </span>
        </button>
      </div>
      {useRemote && (
        <div className="flex flex-col gap-3 pt-2 border-t border-border">
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">Base URL</label>
            <input
              type="text"
              placeholder="http://localhost:8000/v1"
              value={base}
              onChange={(e) => onBaseChange(e.target.value)}
              onBlur={onBlur}
              className="input-theme min-w-0"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">Model</label>
            <input
              type="text"
              placeholder="openai/gpt-oss-20b"
              value={model}
              onChange={(e) => onModelChange(e.target.value)}
              onBlur={onBlur}
              className="input-theme min-w-0"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">API key</label>
            <input
              type="password"
              placeholder="Optional"
              value={apiKey}
              onChange={(e) => onApiKeyChange(e.target.value)}
              onBlur={onBlur}
              className="input-theme min-w-0"
            />
          </div>
        </div>
      )}
    </div>
  );
}
