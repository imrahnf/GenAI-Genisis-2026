"use client";

import React from "react";
import type { Preset } from "../types";

interface PresetsSectionProps {
  presets: Preset[];
  selectedPreset: string | null;
  onSelectPreset: (id: string | null) => void;
  searchQuery?: string;
  onSearchChange?: (q: string) => void;
}

export function PresetsSection({
  presets,
  selectedPreset,
  onSelectPreset,
  searchQuery = "",
  onSearchChange,
}: PresetsSectionProps) {
  const filtered = searchQuery
    ? presets.filter((p) => p.name.toLowerCase().includes(searchQuery.toLowerCase()))
    : presets;

  return (
    <div className="flex flex-col gap-6">
      {onSearchChange && (
        <div className="flex items-center gap-3 px-4 py-3 bg-card border border-border rounded-2xl text-muted-foreground focus-within:border-accent/50 transition-colors max-w-md">
          <input
            type="text"
            placeholder="Search presets"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="flex-1 bg-transparent text-[14px] text-foreground placeholder:text-muted-foreground outline-none"
          />
        </div>
      )}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        {filtered.map((p) => {
          const isSelected = selectedPreset === p.id;
          return (
            <button
              key={p.id}
              type="button"
              onClick={() => onSelectPreset(isSelected ? null : p.id)}
              className={`rounded-2xl overflow-hidden border bg-card text-left transition-all cursor-pointer group ${
                isSelected ? "border-accent/40 ring-1 ring-accent/20" : "border-border hover:border-accent/40"
              }`}
            >
              <div className="h-[100px] overflow-hidden bg-secondary/50 relative" />
              <div className="px-5 py-4 flex flex-col gap-2">
                <p className="text-[15px] text-foreground font-medium">{p.name}</p>
                <div className="flex flex-wrap gap-1.5">
                  <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">
                    Flask · SQLite
                  </span>
                  {p.synthetic_data && (
                    <span className="rounded-full bg-accent/20 text-accent px-2 py-0.5 text-[10px] border border-accent/30">
                      Synthetic data
                    </span>
                  )}
                </div>
                <p className="text-[12px] text-muted-foreground line-clamp-2">{p.description}</p>
              </div>
            </button>
          );
        })}
      </div>
      {filtered.length === 0 && (
        <div className="py-16 text-center text-muted-foreground text-[14px]">
          {searchQuery ? `No presets match "${searchQuery}"` : "No presets loaded."}
        </div>
      )}
    </div>
  );
}
