import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { DEFAULT_BOX_OPACITY } from "../lib/constants";

const read = (p: string) => readFileSync(resolve(__dirname, "..", p), "utf-8");

// The setting is reachable from two places, and they are separate components:
// the main form (CropCaptionSection) and the recut dialog (EditCaptionDialog).
// Adding it to only one is exactly the gap this covers.
const SURFACES = [
  ["main form", "app/_components/sections/CropCaptionSection.tsx"],
  ["edit caption dialog", "app/_components/EditCaptionDialog.tsx"],
] as const;

describe("caption box opacity control", () => {
  it.each(SURFACES)("is offered in the %s", (_label, path) => {
    const source = read(path);
    expect(source).toContain("Opacity Box");
    expect(source).toContain('type="range"');
    expect(source).toContain("DEFAULT_BOX_OPACITY");
  });

  it.each(SURFACES)("only shows for box presets in the %s", (_label, path) => {
    const source = read(path);
    expect(source).toMatch(/captionStyle === "boxed" \|\| captionStyle === "highlight"/);
  });

  it("sends the value with a recut", () => {
    const dialog = read("app/_components/EditCaptionDialog.tsx");
    expect(dialog).toContain("caption_box_opacity: boxOpacity");
    const client = read("lib/apiClient.ts");
    expect(client).toContain("caption_box_opacity?: number | null");
  });

  it("sends the value with a new job", () => {
    expect(read("app/page.tsx")).toContain("caption_box_opacity: captionBoxOpacity");
  });

  it("agrees with the backend defaults", () => {
    // clipper.py: DEFAULT_BOX_OPACITY = {"boxed": 100, "highlight": 45}
    expect(DEFAULT_BOX_OPACITY.boxed).toBe(100);
    expect(DEFAULT_BOX_OPACITY.highlight).toBe(45);
  });
});

describe("caption preview", () => {
  it("reflects the selected preset", () => {
    const source = read("app/_components/CaptionPreview.tsx");
    expect(source).toContain("style?: CaptionStyle");
    expect(source).toContain("presetCss");
  });

  it.each([
    ["ControlPanel", "app/_components/ControlPanel.tsx"],
    ["InspectorPanel", "app/_components/desktop/InspectorPanel.tsx"],
  ])("is given the style by %s", (_label, path) => {
    expect(read(path)).toContain("style={props.captionStyle}");
  });
});
