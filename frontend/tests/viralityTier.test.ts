import { describe, expect, it } from "vitest";
import { VIRALITY_SEGMENTS, viralityTier } from "../lib/utils";

describe("viralityTier", () => {
  it.each([
    [100, "strong"], [92, "strong"], [80, "strong"],
    [79, "good"], [60, "good"],
    [59, "fair"], [40, "fair"],
    [39, "weak"], [0, "weak"],
  ])("reads %i as %s", (score, key) => {
    expect(viralityTier(score as number).key).toBe(key);
  });

  it("gives every score a plain-language verdict", () => {
    for (const score of [0, 25, 50, 75, 100]) {
      expect(viralityTier(score).label.length).toBeGreaterThan(0);
    }
  });

  it("lights segments in proportion to the score", () => {
    expect(viralityTier(0).segments).toBe(0);
    expect(viralityTier(50).segments).toBe(VIRALITY_SEGMENTS / 2);
    expect(viralityTier(100).segments).toBe(VIRALITY_SEGMENTS);
  });

  it("survives missing or out-of-range scores", () => {
    expect(viralityTier(NaN).segments).toBe(0);
    expect(viralityTier(-40).key).toBe("weak");
    expect(viralityTier(999).segments).toBe(VIRALITY_SEGMENTS);
    expect(viralityTier(undefined as unknown as number).key).toBe("weak");
  });
});
