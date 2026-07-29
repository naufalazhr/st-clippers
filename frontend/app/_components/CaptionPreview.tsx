import type React from "react";
import { CAPTION_FONTS } from "../../lib/constants";
import type { CaptionFont, CaptionPosition, WatermarkPosition } from "../../types/clip.type";

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
  watermarkStyle?: WatermarkStyle;
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
// Calibrated against real ffmpeg output: at backend FontSize=30 the rendered
// glyph cap-height is ~6.5% of the 1920px frame. This factor maps the backend
// font size to an equivalent CSS px on the preview so they match visually.
const FONT_CALIBRATION = 0.96;
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
            textShadow: outlineShadow(outline, outlineColor),
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
