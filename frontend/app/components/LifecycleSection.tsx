"use client";

import React from "react";
import LifecycleGraph, { type LifecycleEvent } from "./LifecycleGraph";

interface LifecycleSectionProps {
  events: LifecycleEvent[];
  activeSandboxIds: Set<string>;
}

export function LifecycleSection({ events, activeSandboxIds }: LifecycleSectionProps) {
  if (events.length === 0) {
    return (
      <div className="rounded-2xl border border-border bg-card px-6 py-12 text-center text-muted-foreground text-[14px]">
        No events yet. Launch a sandbox to see the lifecycle graph.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-[13px] text-muted-foreground">
        Event flow: launches (green), recording (red), replays (blue), destroyed (×).
      </p>
      <div className="rounded-2xl border border-border bg-card overflow-hidden">
        <LifecycleGraph events={events} activeSandboxIds={activeSandboxIds} />
      </div>
    </div>
  );
}
