import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const read = (p: string) => readFileSync(resolve(__dirname, "..", p), "utf-8");
const results = read("app/_components/ResultsSection.tsx");
const css = read("app/globals.css");

describe("results board", () => {
  it("shows the score and its verdict per clip", () => {
    expect(results).toContain("viralityTier");
    expect(results).toContain("viralityMeter-score");
    expect(results).toContain("viralityMeter-verdict");
  });

  it("shows why a clip could travel", () => {
    expect(results).toContain("virality_reason");
    expect(results).toContain("Kenapa bisa viral");
  });

  it("ranks clips, since the backend sorted them by score", () => {
    expect(results).toContain("clipRank");
    expect(results).toContain("Diurutkan dari skor viral tertinggi");
  });

  it("does not rank when no clip has a real score", () => {
    // Older jobs have no verdict; a leaderboard there would be meaningless.
    expect(results).toContain("clips.some((clip) => (clip.virality_score ?? 0) > 0)");
  });

  it("keeps every existing action", () => {
    for (const action of ["Buka", "Unduh", "Edit Trim", "Edit Caption", "Copy"]) {
      expect(results).toContain(action);
    }
    expect(results).toContain("ThumbnailPrompt");
    expect(results).toContain("TimelineEditor");
    expect(results).toContain("EditCaptionDialog");
  });

  it("keeps the in-progress states", () => {
    expect(results).toContain("clipCard--pending");
    expect(results).toContain("clipCard--rerendering");
  });

  it("gives the meter an accessible reading", () => {
    expect(results).toContain('role="img"');
    expect(results).toMatch(/aria-label=\{`Skor viral/);
    expect(results).toMatch(/aria-label=\{`Peringkat/);
  });

  it("derives the accent from the tier rather than hardcoding colours", () => {
    for (const tier of ["strong", "good", "fair", "weak"]) {
      expect(css).toContain(`.clipCard[data-tier="${tier}"]`);
    }
    expect(css).toContain("--tier: var(--success)");
  });

  it("respects reduced motion and narrow windows", () => {
    expect(css).toContain("prefers-reduced-motion");
    expect(css).toContain("@media (max-width: 560px)");
  });
});

describe("topic input", () => {
  it("is offered on the creation form", () => {
    const source = read("app/_components/sections/SourceSection.tsx");
    expect(source).toContain("Topik yang Disorot");
    expect(source).toContain("onTopicChange");
    expect(source).toContain("maxLength={300}");
  });

  it("is sent with the job", () => {
    expect(read("app/page.tsx")).toContain("topic: topic.trim()");
  });
});
