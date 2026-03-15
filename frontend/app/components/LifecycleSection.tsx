"use client";

import React from "react";
import { GitBranch } from "lucide-react";
import LifecycleGraph, { type LifecycleEvent } from "./LifecycleGraph";

interface LifecycleSectionProps {
  events: LifecycleEvent[];
  activeSandboxIds: Set<string>;
}

export function LifecycleSection({ events, activeSandboxIds }: LifecycleSectionProps) {
  if (events.length === 0) {
    return (
      <div className="card-dev px-6 py-16 text-center">
        <div className="flex justify-center mb-3">
          <GitBranch size={28} className="text-zinc-500" />
        </div>
        <p className="text-zinc-400 text-[14px] font-medium">No events yet</p>
        <p className="text-zinc-500 text-[13px] mt-1">Launch a sandbox to see the lifecycle graph.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-[13px] text-zinc-400">
        Event flow: launches (green), recording (red), replays (blue), destroyed (×).
      </p>
      <div className="card-dev overflow-hidden">
        <LifecycleGraph events={events} activeSandboxIds={activeSandboxIds} />
      </div>
    </div>
  );
}
