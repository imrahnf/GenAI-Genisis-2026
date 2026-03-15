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
    <div className="card-dev flex flex-col gap-4 p-4 max-w-lg">
      <p className="text-[13px] text-zinc-400">LLM backend used by agents for commands and planning.</p>
      <div className="flex items-center gap-3">
        <span className="text-xs font-medium text-zinc-50 font-sans">Provider</span>
        <button
          type="button"
          role="switch"
          aria-checked={useRemote}
          onClick={() => onUseRemoteChange(!useRemote)}
          className="relative inline-flex h-8 w-[11rem] flex-shrink-0 rounded-full border border-zinc-700 bg-zinc-900 transition-colors focus:outline-none focus:ring-2 focus:ring-cyan-400/30"
        >
          <span
            className={`pointer-events-none absolute inset-y-1 flex h-6 w-[5.25rem] items-center justify-center rounded-full text-xs font-medium transition-all text-white ${
              useRemote ? "left-[calc(100%-5.5rem)] bg-cyan-500 text-zinc-950" : "left-1 bg-zinc-800 border border-zinc-700"
            }`}
          >
            {useRemote ? "Remote" : "IBM Watson"}
          </span>
        </button>
      </div>
      {useRemote && (
        <div className="flex flex-col gap-3 pt-2 border-t border-zinc-800">
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-medium uppercase tracking-wider text-zinc-500 font-sans">Base URL</label>
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
            <label className="text-[10px] font-medium uppercase tracking-wider text-zinc-500 font-sans">Model</label>
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
            <label className="text-[10px] font-medium uppercase tracking-wider text-zinc-500 font-sans">API key</label>
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
