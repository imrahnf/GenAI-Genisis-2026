"use client";

import React from "react";
import Link from "next/link";
import { ExternalLink, Video, RotateCcw, Trash2, CheckCircle, AlertCircle, FileText, Server } from "lucide-react";
import type { Sandbox } from "../types";

function formatExpires(expiresAt: number | string | null | undefined): string {
  if (expiresAt == null || expiresAt === "") return "—";
  const t = typeof expiresAt === "string" ? parseFloat(expiresAt) : expiresAt;
  if (Number.isNaN(t)) return "—";
  const d = new Date(t * 1000);
  const now = Date.now();
  if (d.getTime() <= now) return "expired";
  const minLeft = Math.round((d.getTime() - now) / 60000);
  return `${d.toLocaleTimeString()} (in ${minLeft} min)`;
}

interface SandboxesSectionProps {
  sandboxes: Sandbox[];
  expandedLogs: string | null;
  captureSaveName: { id: string; name: string } | null;
  onExpandLogs: (sandboxId: string | null) => void;
  onCaptureSaveName: (v: { id: string; name: string } | null) => void;
  onCaptureStart: (sandboxId: string) => void;
  onCaptureStop: (sandboxId: string, saveAsTemplate: boolean, name: string) => void;
  onReset: (sandboxId: string) => void;
  onDestroy: (sandboxId: string) => void;
}

export function SandboxesSection({
  sandboxes,
  expandedLogs,
  captureSaveName,
  onExpandLogs,
  onCaptureSaveName,
  onCaptureStart,
  onCaptureStop,
  onReset,
  onDestroy,
}: SandboxesSectionProps) {
  if (sandboxes.length === 0) {
    return (
      <div className="card-dev px-6 py-16 text-center">
        <div className="flex justify-center mb-3">
          <Server size={28} className="text-muted-foreground" />
        </div>
        <p className="text-muted-foreground text-[14px] font-medium">No sandboxes</p>
        <p className="text-muted-foreground/80 text-[13px] mt-1">Select a preset and launch from Presets.</p>
      </div>
    );
  }

  return (
    <div className="card-dev overflow-hidden">
      <div className="flex items-center gap-4 px-5 py-3 border-b border-[#363636] bg-secondary">
        <span className="text-[11px] text-muted-foreground uppercase tracking-wider w-[100px] font-sans">Preset</span>
        <span className="text-[11px] text-muted-foreground uppercase tracking-wider flex-1 min-w-0 font-sans">URL</span>
        <span className="text-[11px] text-muted-foreground uppercase tracking-wider hidden md:block flex-1 min-w-0 truncate font-sans">Goal</span>
        <span className="text-[11px] text-muted-foreground uppercase tracking-wider w-[100px] font-sans">Expires</span>
        <div className="w-[200px] flex-shrink-0 flex items-center justify-end gap-2">
          <span className="flex items-center gap-1.5 text-[11px] text-accent font-mono">
            <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
            Live
          </span>
        </div>
      </div>
      {sandboxes.map((s, index) => {
        const isExpired = formatExpires(s.expires_at) === "expired";
        const isLogsExpanded = expandedLogs === s.sandbox_id;
        const isCapturing = s.capture_active;
        const showSaveInput = captureSaveName?.id === s.sandbox_id;
        return (
          <React.Fragment key={s.sandbox_id}>
            <div
              className={`flex flex-wrap items-center gap-4 px-5 py-4 hover:bg-secondary/80 transition-colors ${
                index !== sandboxes.length - 1 && !isLogsExpanded ? "border-b border-[#363636]" : ""
              }`}
            >
              <div className="w-[100px] flex items-center gap-2 min-w-0">
                <span className="text-[13px] text-foreground font-medium truncate font-mono">{s.preset ?? "preset"}</span>
                {s.template_id && (
                  <span className="rounded-full bg-amber-500/20 text-amber-400 px-1.5 py-0.5 text-[10px] border border-amber-500/30">
                    Replay
                  </span>
                )}
              </div>
              <div className="flex-1 min-w-0 flex items-center gap-2">
                <a
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-[12px] text-muted-foreground hover:text-foreground truncate min-w-0 font-mono"
                >
                  {s.url}
                  <ExternalLink size={12} className="flex-shrink-0" />
                </a>
                <Link
                  href={`/sandbox/${s.sandbox_id}`}
                  className="text-[11px] text-accent hover:text-accent/90 flex-shrink-0 font-mono"
                >
                  Details
                </Link>
              </div>
              <p className="hidden md:block flex-1 min-w-0 truncate text-[12px] text-muted-foreground" title={s.goal}>
                {s.goal}
              </p>
              <div className="w-[100px] flex items-center gap-1.5 flex-shrink-0">
                {isExpired ? (
                  <AlertCircle size={13} className="text-destructive flex-shrink-0" />
                ) : (
                  <CheckCircle size={13} className="text-accent flex-shrink-0" />
                )}
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] font-mono ${
                    isExpired ? "bg-destructive/20 text-destructive" : "bg-secondary text-muted-foreground"
                  }`}
                >
                  {isExpired ? "Expired" : formatExpires(s.expires_at)}
                </span>
              </div>
              <div className="w-full md:w-auto flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => onExpandLogs(isLogsExpanded ? null : s.sandbox_id)}
                  className="btn-ghost text-xs"
                >
                  Logs{s.logs?.length ? ` (${s.logs.length})` : ""}
                </button>
                {isCapturing ? (
                  <>
                    <span className="text-[10px] text-muted-foreground font-mono">Recording ({s.capture_steps_count ?? 0})</span>
                    <button
                      type="button"
                      onClick={() => onCaptureSaveName({ id: s.sandbox_id, name: "" })}
                      className="btn-ghost inline-flex items-center gap-1 text-xs"
                    >
                      <Video size={14} />
                      Stop & save
                    </button>
                    {showSaveInput && (
                      <span className="flex items-center gap-2">
                        <input
                          type="text"
                          placeholder="Template name"
                          value={captureSaveName!.name}
                          onChange={(e) => onCaptureSaveName({ ...captureSaveName!, name: e.target.value })}
                          className="input-theme w-28 text-xs"
                        />
                        <button
                          type="button"
                          onClick={() => onCaptureStop(s.sandbox_id, true, captureSaveName!.name)}
                          className="btn-ghost text-xs"
                        >
                          Save
                        </button>
                        <button
                          type="button"
                          onClick={() => onCaptureStop(s.sandbox_id, false, "")}
                          className="btn-ghost text-xs"
                        >
                          Cancel
                        </button>
                      </span>
                    )}
                  </>
                ) : (
                  <button
                    type="button"
                    onClick={() => onCaptureStart(s.sandbox_id)}
                    className="btn-ghost inline-flex items-center gap-1 rounded-lg bg-accent/20 px-3 py-2 text-xs text-accent hover:bg-accent/30"
                  >
                    <Video size={14} />
                    Capture
                  </button>
                )}
                <button type="button" onClick={() => onReset(s.sandbox_id)} className="btn-ghost text-xs">
                  <RotateCcw size={14} />
                  Reset
                </button>
                <button type="button" onClick={() => onDestroy(s.sandbox_id)} className="btn-destroy text-xs">
                  <Trash2 size={14} />
                  Destroy
                </button>
              </div>
            </div>
            {isLogsExpanded && (
              <div className="border-t border-[#363636] bg-secondary px-5 py-3">
                <div className="mb-2 flex items-center gap-2">
                  <FileText size={14} className="text-muted-foreground" />
                  <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground font-sans">Agent logs</span>
                  {s.logs && s.logs.length > 0 && (
                    <span className="flex items-center gap-1.5 text-[11px] text-accent ml-auto font-mono">
                      <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                      Live
                    </span>
                  )}
                </div>
                {!s.logs?.length ? (
                  <p className="text-muted-foreground text-sm font-mono">No logs.</p>
                ) : (
                  <div className="max-h-56 overflow-auto space-y-1 font-mono text-[11px]">
                    {s.logs.map((l, i) => (
                      <div key={i} className="flex items-start gap-3 text-muted-foreground hover:text-foreground transition-colors py-0.5">
                        <span className="text-muted-foreground/80 flex-shrink-0 w-[70px]">{new Date(l.ts * 1000).toISOString().slice(11, 19)}</span>
                        <span
                          className={`flex-shrink-0 w-[52px] ${
                            l.type === "error" ? "text-destructive" : l.type === "llm" ? "text-accent" : "text-muted-foreground"
                          }`}
                        >
                          [{l.type}]
                        </span>
                        <span className="text-foreground flex-1 break-all">{l.message}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}
