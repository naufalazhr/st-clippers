import toast from "react-hot-toast";
import type { ClipJob } from "../types/clip.type";

export function isActiveJob(job: ClipJob | null) {
  return job?.status === "queued" || job?.status === "running";
}

export function clipTitle(name: string) {
  return name.replace(/\.mp4$/i, "").replace(/^clip_\d+_/, "").replace(/-/g, " ");
}

async function downloadClip(url: string, filename: string) {
  const response = await fetch(url);
  if (!response.ok) throw new Error("Gagal mengunduh file");

  const blob = await response.blob();
  const blobUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = blobUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(blobUrl);
}

export async function handleDownload(url: string, filename: string) {
  toast
    .promise(downloadClip(url, filename), {
      loading: "Mengunduh klip...",
      success: "Klip berhasil diunduh!",
      error: "Gagal mengunduh klip",
    })
    .catch(() => {
      window.open(url, "_blank");
    });
}

export async function handleCopyTitle(title: string) {
  await navigator.clipboard.writeText(title);
  toast.success("Judul klip berhasil disalin");
}

export async function handleCopyText(text: string, message = "Berhasil disalin") {
  await navigator.clipboard.writeText(text);
  toast.success(message);
}


/**
 * How many placeholder tiles to show while a job is still rendering.
 *
 * The backend publishes each clip as it finishes, so the difference between the
 * requested count and what has arrived is what is still being worked on.
 */
export const pendingClipCount = (
  status: string | undefined,
  expected: number | null | undefined,
  readyCount: number,
): number => {
  if (status !== "running" && status !== "queued") return 0;
  return Math.max(0, (expected ?? 0) - readyCount);
};


/**
 * Run `load` until it succeeds, for use on startup fetches.
 *
 * The desktop backend is a frozen sidecar that takes a few seconds to bind, so
 * the first call from a freshly opened window often fails. Swallowing that
 * failure left the history empty for the whole session even though the jobs
 * were on disk. Returns true if a load eventually succeeded.
 */
export const loadWithRetry = async (
  load: () => Promise<unknown>,
  options: {
    attempts: number;
    delayMs: number;
    sleep?: (ms: number) => Promise<void>;
    isCancelled?: () => boolean;
  },
): Promise<boolean> => {
  const sleep =
    options.sleep ?? ((ms: number) => new Promise<void>((r) => setTimeout(r, ms)));

  for (let attempt = 0; attempt < options.attempts; attempt += 1) {
    if (options.isCancelled?.()) return false;
    try {
      await load();
      return true;
    } catch {
      if (attempt === options.attempts - 1) return false;
      await sleep(options.delayMs);
    }
  }
  return false;
};
