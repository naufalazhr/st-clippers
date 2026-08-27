import type React from "react";
import { CAPTION_FONTS, DEFAULT_BOX_OPACITY } from "../../lib/constants";
import type { CaptionFont, CaptionPosition, CaptionStyle, WatermarkPosition } from "../../types/clip.type";

type WatermarkStyle = {
  type: "text" | "image";
  text?: string;
  imageUrl?: string;
  position: WatermarkPosition;
  opacity: number;
  scale: number;
  fontFamily?: string;
  color?: string;
};

type CaptionPreviewProps = {
  fontSize: number;
  position: CaptionPosition;
  color: string;
  font: CaptionFont;
  outline: number;
  outlineColor: string;
  /** Preset the clip is rendered with. Without this the preview looked
   *  identical for every style, so switching styles appeared to do nothing. */
  style?: CaptionStyle;
  /** 0-100 opacity of the box behind boxed/highlight text. */
  boxOpacity?: number | null;
  watermarkStyle?: WatermarkStyle;
};

const hexToRgba = (hex: string, alpha: number): string => {
  let value = hex.trim().replace("#", "");
  if (value.length === 3) value = value.split("").map((c) => c + c).join("");
  if (value.length !== 6) return `rgba(0, 0, 0, ${alpha})`;
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(value.slice(i, i + 2), 16));
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};

/** CSS that matches what build_subtitle_style() produces for each preset. */
const presetCss = (
  style: CaptionStyle,
  outline: number,
  outlineColor: string,
  boxOpacity: number | null | undefined,
): React.CSSProperties => {
  if (style === "boxed" || style === "highlight") {
    const percent = boxOpacity ?? DEFAULT_BOX_OPACITY[style] ?? 100;
    return {
      // BorderStyle=3: an opaque plate in OutlineColour, padded by Outline.
      background: hexToRgba(outlineColor, Math.max(0, Math.min(100, percent)) / 100),
      padding: `0.1em ${Math.max(0.15, outline * 0.12)}em`,
      textShadow: "none",
      boxDecorationBreak: "clone",
      WebkitBoxDecorationBreak: "clone",
    };
  }
  if (style === "shadow") {
    return { textShadow: `2px 2px 3px ${hexToRgba(outlineColor, 0.9)}` };
  }
  if (style === "bold") {
    return { textShadow: outlineShadow(outline + 1, outlineColor), fontWeight: 900 };
  }
  return { textShadow: outlineShadow(outline, outlineColor) };
};

const POSITION_STYLE: Record<WatermarkPosition, React.CSSProperties> = {
  "top-left":      { top: "5%", left: "5%" },
  "top-center":    { top: "5%", left: "50%", transform: "translateX(-50%)" },
  "top-right":     { top: "5%", right: "5%" },
  "middle-left":   { top: "50%", left: "5%", transform: "translateY(-50%)" },
  "middle-center": { top: "50%", left: "50%", transform: "translate(-50%, -50%)" },
  "middle-right":  { top: "50%", right: "5%", transform: "translateY(-50%)" },
  "bottom-left":   { bottom: "5%", left: "5%" },
  "bottom-center": { bottom: "5%", left: "50%", transform: "translateX(-50%)" },
  "bottom-right":  { bottom: "5%", right: "5%" },
};

const PREVIEW_HEIGHT = 320;
// libass renders the burned-in captions against the default ASS script height
// (PlayResY=288), so a backend FontSize of N occupies N/288 of the frame height
// whatever the output resolution. Matching that on a PREVIEW_HEIGHT-tall stage
// means scaling by PREVIEW_HEIGHT/288 -- the previous hand-tuned 0.96 drew the
// preview 14% smaller than the clip it was predicting.
const ASS_SCRIPT_HEIGHT = 288;
const FONT_CALIBRATION = PREVIEW_HEIGHT / ASS_SCRIPT_HEIGHT;
const SAMPLE_TEXT = "Contoh caption di video kamu";

function outlineShadow(width: number, color: string): string {
  if (width <= 0) return "none";
  // Preview canvas is ~1/6 of the real frame, scale the border to match.
  const w = Math.max(0.5, (width * PREVIEW_HEIGHT) / 1920 * 6);
  const offsets: string[] = [];
  for (let x = -w; x <= w; x += w) {
    for (let y = -w; y <= w; y += w) {
      if (x === 0 && y === 0) continue;
      offsets.push(`${x}px ${y}px 0 ${color}`);
    }
  }
  return offsets.join(", ");
}

export function CaptionPreview({
  fontSize,
  position,
  color,
  font,
  outline,
  outlineColor,
  style = "classic",
  boxOpacity,
  watermarkStyle,
}: CaptionPreviewProps) {
  const scaledFont = fontSize * FONT_CALIBRATION;
  const fontCss = CAPTION_FONTS.find((item) => item.value === font)?.css ?? "sans-serif";

  return (
    <div className="captionPreview">
      <span className="captionPreviewLabel">Preview</span>
      <div
        className="captionPreviewStage"
        style={{ height: PREVIEW_HEIGHT, aspectRatio: "9 / 16", position: "relative" }}
      >
        <div
          className={`captionPreviewText captionPreviewText--${position}`}
          style={{
            fontSize: `${scaledFont}px`,
            color,
            fontFamily: fontCss,
            ...presetCss(style, outline, outlineColor, boxOpacity),
          }}
        >
          {SAMPLE_TEXT}
        </div>

        {watermarkStyle && (
          <div
            style={{
              position: "absolute",
              ...POSITION_STYLE[watermarkStyle.position],
              opacity: watermarkStyle.opacity / 100,
              pointerEvents: "none",
              maxWidth: "80%",
            }}
          >
            {watermarkStyle.type === "text" && watermarkStyle.text && (
              <span
                style={{
                  fontSize: `${(watermarkStyle.scale / 100) * 12}px`,
                  color: watermarkStyle.color ?? "#ffffff",
                  fontFamily: CAPTION_FONTS.find((f) => f.value === watermarkStyle.fontFamily)?.css ?? "sans-serif",
                  whiteSpace: "nowrap",
                }}
              >
                {watermarkStyle.text}
              </span>
            )}
            {watermarkStyle.type === "image" && watermarkStyle.imageUrl && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={watermarkStyle.imageUrl}
                alt="watermark"
                style={{ width: `${watermarkStyle.scale}%`, maxWidth: "100%" }}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
