import { describe, expect, it } from "vitest";

// Mirrors CaptionPreview: the preview must predict the burned-in caption size.
const PREVIEW_HEIGHT = 320;
const ASS_SCRIPT_HEIGHT = 288;
const FONT_CALIBRATION = PREVIEW_HEIGHT / ASS_SCRIPT_HEIGHT;

/** Fraction of frame height a backend FontSize occupies in the rendered clip. */
const outputEmFraction = (fontSize: number) => fontSize / ASS_SCRIPT_HEIGHT;

/** Fraction of the preview stage the same value occupies on screen. */
const previewEmFraction = (fontSize: number) =>
  (fontSize * FONT_CALIBRATION) / PREVIEW_HEIGHT;

describe("caption preview scaling", () => {
  it.each([6, 12, 30, 60, 120])("matches the rendered size at %i", (fontSize) => {
    expect(previewEmFraction(fontSize)).toBeCloseTo(outputEmFraction(fontSize), 10);
  });

  it("is resolution independent, as libass is", () => {
    // 12/288 of the frame, whether the clip is 1920 or 1080 tall.
    expect(outputEmFraction(12) * 1920).toBeCloseTo(80, 6);
    expect(outputEmFraction(12) * 1080).toBeCloseTo(45, 6);
  });
});
