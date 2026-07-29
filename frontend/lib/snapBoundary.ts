import type { TranscriptSegment } from "../types/clip.type";

/**
 * Snap a time value to the nearest transcript segment boundary if within 0.4s.
 * Clamps result to [0, duration].
 */
export function snapBoundary(time: number, segments: TranscriptSegment[], duration: number): number {
  let best = time;
  let bestDist = 0.4;
  for (const s of segments) {
    for (const t of [s.start, s.end]) {
      const dist = Math.abs(time - t);
      if (dist < bestDist) {
        bestDist = dist;
        best = t;
      }
    }
  }
  return Math.max(0, Math.min(best, duration));
}
