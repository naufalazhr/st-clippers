import { useEffect } from "react";

export function isInTauri(): boolean {
  try {
    return typeof window !== "undefined" &&
      typeof (window as unknown as Record<string, unknown>)["__TAURI_INTERNALS__"] !== "undefined";
  } catch { return false; }
}

export type MenuAction = { item_id: string };

export const MENU_IDS = {
  newJob: "file.new-job",
  openVideo: "file.open-video",
  refresh: "view.refresh",
  theme: "view.theme",
  sidebar: "view.sidebar",
  statusbar: "view.statusbar",
  about: "help.about",
  docs: "help.docs",
} as const;

export function useMenuActions(onAction: (itemId: string) => void): void {
  useEffect(() => {
    if (!isInTauri()) return;
    let unlisten: (() => void) | undefined;
    let cancelled = false;
    (async () => {
      const { listen } = await import("@tauri-apps/api/event");
      const fn = await listen<MenuAction>("menu-action", (e) => onAction(e.payload.item_id));
      if (cancelled) fn(); else unlisten = fn;
    })();
    return () => { cancelled = true; unlisten?.(); };
  }, [onAction]);
}

export async function openExternal(url: string): Promise<void> {
  if (!isInTauri()) { window.open(url, "_blank"); return; }
  const { open } = await import("@tauri-apps/plugin-shell");
  await open(url);
}
