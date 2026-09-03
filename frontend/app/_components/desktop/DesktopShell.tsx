"use client";

import type { ReactNode } from "react";
import "./DesktopShell.css";

export type DesktopView = "clip" | "history" | "editor" | "settings";

export interface DesktopShellProps {
  view: DesktopView;
  onViewChange: (view: DesktopView) => void;
  showSidebar: boolean;
  showStatusbar: boolean;
  onToggleSidebar: () => void;
  onToggleStatusbar: () => void;
  sidebar: ReactNode;
  canvas: ReactNode;
  statusbar: ReactNode;
}

export function DesktopShell({
  showSidebar,
  showStatusbar,
  sidebar,
  canvas,
  statusbar,
}: DesktopShellProps) {
  return (
    <div
      className="desktopShell"
      data-sidebar={showSidebar}
    >
      {showSidebar && (
        <div className="desktopShell-sidebar">{sidebar}</div>
      )}
      <div className="desktopShell-canvas">{canvas}</div>
      {showStatusbar && (
        <div className="desktopShell-statusbar">{statusbar}</div>
      )}
    </div>
  );
}
