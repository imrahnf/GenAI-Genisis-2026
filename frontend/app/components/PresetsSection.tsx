"use client";

import React from "react";
import Image from "next/image";
import { Search, X, FolderOpen } from "lucide-react";
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
        <div className="card-dev flex items-center gap-3 px-4 py-3 text-muted-foreground focus-within:border-accent/50 transition-colors max-w-md">
          <Search size={15} className="flex-shrink-0 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search presets"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="flex-1 bg-transparent text-[14px] text-foreground placeholder:text-muted-foreground outline-none min-w-0"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => onSearchChange("")}
              className="flex-shrink-0 p-1 rounded-lg hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors"
              aria-label="Clear search"
            >
              <X size={14} />
            </button>
          )}
        </div>
      )}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        {filtered.map((p) => {
          const isSelected = selectedPreset === p.id;
          const nameLower = p.name.toLowerCase();
          const isSpending = p.id === "spending" || nameLower.includes("spending & anomaly");
          const isFood = p.id === "preset" || nameLower.includes("favorite foods");
          const isBank = p.id === "bank" || nameLower.includes("bank");

          let thumbSrc: string | null = null;
          if (isSpending) thumbSrc = "/opengraph-image.png";
          else if (isFood) thumbSrc = "/food.png";
          else if (isBank) thumbSrc = "/bank.png";

          return (
            <button
              key={p.id}
              type="button"
              onClick={() => onSelectPreset(isSelected ? null : p.id)}
              className={`card-dev overflow-hidden text-left transition-all duration-300 cursor-pointer group hover:translateY(-2px) ${
                isSelected ? "border-accent/50 ring-1 ring-accent/20" : "hover:border-[#404040]"
              }`}
            >
              {thumbSrc ? (
                <div className="h-[100px] overflow-hidden relative">
                  <Image src={thumbSrc} alt={p.name} fill className="object-cover opacity-85" />
                </div>
              ) : (
                <div className="h-[100px] overflow-hidden bg-secondary/80 relative transition-all duration-300 group-hover:opacity-90" />
              )}
              <div className="px-5 py-4 flex flex-col gap-2">
                <p className="text-[15px] text-foreground font-medium font-sans tracking-tight">{p.name}</p>
                <div className="flex flex-wrap gap-1.5">
                  <span className="rounded-full bg-[#404040] px-2 py-0.5 text-[10px] text-muted-foreground font-mono">
                    Flask · SQLite
                  </span>
                  {p.synthetic_data && (
                    <span className="rounded-full bg-accent-light/20 text-accent-light px-2 py-0.5 text-[10px] border border-accent-light/40 font-mono">
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
        <div className="py-16 text-center">
          <div className="flex justify-center mb-3">
            <FolderOpen size={28} className="text-muted-foreground" />
          </div>
          <p className="text-muted-foreground text-[14px] font-medium">
            {searchQuery ? `No presets match "${searchQuery}"` : "No presets loaded."}
          </p>
          {!searchQuery && (
            <p className="text-muted-foreground/80 text-[13px] mt-1">Check the backend is running.</p>
          )}
        </div>
      )}
    </div>
  );
}
