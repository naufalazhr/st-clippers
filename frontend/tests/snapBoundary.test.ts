import { describe, it, expect } from "vitest";
import { snapBoundary } from "../lib/snapBoundary";
import type { TranscriptSegment } from "../types/clip.type";

const duration = 100;

describe("snapBoundary", () => {
  it("returns time unchanged when segments array is empty", () => {
    expect(snapBoundary(5, [], duration)).toBe(5);
  });

  it("snaps to exact segment boundary when time matches exactly", () => {
    const segments: TranscriptSegment[] = [{ start: 10, end: 20, text: "hello" }];
    expect(snapBoundary(10, segments, duration)).toBe(10);
    expect(snapBoundary(20, segments, duration)).toBe(20);
  });

  it("snaps to nearest boundary when time is within 0.4s", () => {
    const segments: TranscriptSegment[] = [
      { start: 10, end: 20, text: "a" },
      { start: 25, end: 35, text: "b" },
    ];
    // 10.3 is 0.3s from boundary 10 — should snap
    expect(snapBoundary(10.3, segments, duration)).toBe(10);
    // 24.7 is 0.3s from boundary 25 — should snap
    expect(snapBoundary(24.7, segments, duration)).toBe(25);
  });

  it("does not snap when time is more than 0.4s from all boundaries", () => {
    const segments: TranscriptSegment[] = [{ start: 10, end: 20, text: "a" }];
    // 15 is 5s from both 10 and 20 — no snap
    expect(snapBoundary(15, segments, duration)).toBe(15);
  });

  it("picks the nearest boundary when between two segments", () => {
    const segments: TranscriptSegment[] = [
      { start: 10, end: 20, text: "a" },
      { start: 20.2, end: 30, text: "b" },
    ];
    // 20.05 is 0.05 from 20 and 0.15 from 20.2 — picks 20
    expect(snapBoundary(20.05, segments, duration)).toBe(20);
    // 20.15 is 0.15 from 20 and 0.05 from 20.2 — picks 20.2
    expect(snapBoundary(20.15, segments, duration)).toBe(20.2);
  });

  it("clamps negative time to 0", () => {
    expect(snapBoundary(-5, [], duration)).toBe(0);
  });

  it("clamps time past duration to duration", () => {
    expect(snapBoundary(150, [], duration)).toBe(duration);
  });

  it("clamps snapped boundary result to [0, duration]", () => {
    // boundary at 0 — clamping should still work
    const segments: TranscriptSegment[] = [{ start: 0, end: 50, text: "a" }];
    expect(snapBoundary(-0.1, segments, duration)).toBe(0);
  });
});
