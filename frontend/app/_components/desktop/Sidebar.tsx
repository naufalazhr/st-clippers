"use client";

import { History, PanelLeft, Scissors, Settings, Sliders } from "lucide-react";
import type { DesktopView } from "./DesktopShell";
import "./Sidebar.css";

export interface SidebarProps {
  view: DesktopView;
  onViewChange: (view: DesktopView) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
}

const NAV_ITEMS: { id: DesktopView; label: string; icon: typeof Scissors }[] = [
  { id: "editor", label: "Editor", icon: Sliders },
  { id: "clip", label: "New Clip", icon: Scissors },
  { id: "history", label: "History", icon: History },
  { id: "settings", label: "Settings", icon: Settings },
];

export function Sidebar({ view, onViewChange, collapsed, onToggleCollapse }: SidebarProps) {
  return (
    <aside className="sidebar" data-collapsed={collapsed}>
      <div className="sidebar-brand">
        <span className="wordmark">Sultan Clip</span>
      </div>

      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            className="sidebar-navItem"
            data-active={view === item.id}
            onClick={() => onViewChange(item.id)}
            title={collapsed ? item.label : undefined}
          >
            <span className="sidebar-navItem-icon">
              <item.icon size={18} />
            </span>
            <span className="sidebar-navItem-label">{item.label}</span>
          </button>
        ))}
      </nav>

      <div className="sidebar-footer">
        <button
          className="sidebar-collapseBtn"
          onClick={onToggleCollapse}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <span className="sidebar-navItem-icon">
            <PanelLeft size={18} />
          </span>
          <span className="sidebar-collapseBtn-label">Collapse</span>
        </button>
        <span className="sidebar-version">v1.0.0</span>
      </div>
    </aside>
  );
}
