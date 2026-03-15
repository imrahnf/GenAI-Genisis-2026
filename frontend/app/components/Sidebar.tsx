"use client";

import { FolderOpen, Play, Server, Network, Settings, User, ChevronDown } from "lucide-react";

export type Section = "presets" | "replays" | "sandboxes" | "lifecycle";

const navItems: { id: Section; label: string; icon: React.ElementType }[] = [
  { id: "presets", label: "Presets", icon: FolderOpen },
  { id: "replays", label: "Replays", icon: Play },
  { id: "sandboxes", label: "Sandboxes", icon: Server },
  { id: "lifecycle", label: "Lifecycle", icon: Network },
];

interface SidebarProps {
  activeSection: Section;
  onNavigate: (section: Section) => void;
  onSettingsClick?: () => void;
  sandboxesCount?: number;
}

export function Sidebar({ activeSection, onNavigate, onSettingsClick, sandboxesCount = 0 }: SidebarProps) {
  return (
    <aside className="w-[240px] min-w-[240px] h-screen flex flex-col bg-background border-r border-[#363636] flex-shrink-0">
      <div className="px-5 py-5 border-b border-[#363636]">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center">
            <span className="font-sans text-[18px] font-semibold tracking-tight text-white leading-none">D</span>
          </div>
          <div>
            <p className="text-[13px] text-foreground leading-tight">DemoForge</p>
            <p className="text-[11px] text-muted-foreground leading-tight">Sandbox · Deploy</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 px-3 py-2 flex flex-col gap-0.5">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = item.id === activeSection;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onNavigate(item.id)}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13px] text-left w-full transition-colors ${
                isActive
                  ? "bg-secondary text-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-secondary/80"
              }`}
            >
              <Icon size={14} />
              {item.label}
              {item.id === "sandboxes" && sandboxesCount > 0 && (
                <span className="ml-auto text-[10px] bg-accent text-accent-foreground px-1.5 py-0.5 rounded-full">
                  {sandboxesCount}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      <div className="px-3 py-3 border-t border-[#363636] flex flex-col gap-0.5">
        <button
          type="button"
          onClick={onSettingsClick}
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-[12px] text-muted-foreground hover:text-foreground hover:bg-secondary/80 w-full transition-colors"
        >
          <Settings size={13} />
          Settings
        </button>
        <button
          type="button"
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-[12px] text-muted-foreground hover:text-foreground hover:bg-secondary/80 w-full transition-colors"
        >
          <div className="w-5 h-5 rounded-full bg-[#404040] border border-[#363636] flex items-center justify-center">
            <User size={11} />
          </div>
          <span className="flex-1 text-left">developer</span>
          <ChevronDown size={11} />
        </button>
      </div>
    </aside>
  );
}
