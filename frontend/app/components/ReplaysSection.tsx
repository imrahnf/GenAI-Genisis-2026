"use client";

import React from "react";
import { Play } from "lucide-react";
import type { Template } from "../types";

interface ReplaysSectionProps {
  templates: Template[];
  onLaunchReplay: (template: Template) => void;
  loading?: boolean;
}

export function ReplaysSection({ templates, onLaunchReplay, loading }: ReplaysSectionProps) {
  if (templates.length === 0) {
    return (
      <div className="border border-border rounded-2xl bg-card overflow-hidden">
        <div className="px-6 py-12 text-center text-muted-foreground text-[14px]">
          No templates yet. Start a sandbox, click Capture, then Stop & save.
        </div>
      </div>
    );
  }

  return (
    <div className="border border-border rounded-2xl bg-card overflow-hidden">
      <div className="flex items-center gap-4 px-5 py-3 border-b border-border bg-secondary/20">
        <span className="text-[11px] text-muted-foreground uppercase tracking-wider w-[200px]">Template</span>
        <span className="text-[11px] text-muted-foreground uppercase tracking-wider flex-1">Preset</span>
        <span className="text-[11px] text-muted-foreground uppercase tracking-wider w-[80px]">Steps</span>
        <div className="w-[120px]" />
      </div>
      {templates.map((t, index) => (
        <div
          key={t.id}
          className={`flex items-center gap-4 px-5 py-4 hover:bg-secondary/30 transition-colors ${
            index !== templates.length - 1 ? "border-b border-border" : ""
          }`}
        >
          <p className="text-[13px] text-foreground font-medium w-[200px] truncate">{t.name}</p>
          <span className="rounded-full bg-secondary px-2 py-0.5 text-[11px] text-muted-foreground">{t.preset}</span>
          <span className="text-[12px] text-muted-foreground w-[80px]">{t.steps_count} steps</span>
          <button
            type="button"
            onClick={() => onLaunchReplay(t)}
            disabled={loading}
            className="btn-primary flex items-center gap-1.5 px-4 py-2 text-xs"
          >
            <Play size={14} />
            Launch replay
          </button>
        </div>
      ))}
    </div>
  );
}
