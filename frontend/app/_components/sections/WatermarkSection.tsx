"use client";

import { CAPTION_FONTS } from "../../../lib/constants";
import type { WatermarkPosition, WatermarkType } from "../../../types/clip.type";

type WatermarkSectionProps = {
  watermarkType: WatermarkType;
  onWatermarkTypeChange: (value: WatermarkType) => void;
  watermarkText: string;
  onWatermarkTextChange: (value: string) => void;
  watermarkPosition: WatermarkPosition;
  onWatermarkPositionChange: (value: WatermarkPosition) => void;
  watermarkOpacity: number;
  onWatermarkOpacityChange: (value: number) => void;
  watermarkScale: number;
  onWatermarkScaleChange: (value: number) => void;
  watermarkFontFamily: string;
  onWatermarkFontFamilyChange: (value: string) => void;
  watermarkColor: string;
  onWatermarkColorChange: (value: string) => void;
  watermarkImage: File | null;
  onWatermarkImageChange: (file: File | null) => void;
  uploadedImageUrl: string | null;
};

const POSITION_GRID: { value: WatermarkPosition; label: string }[] = [
  { value: "top-left",      label: "↖" },
  { value: "top-center",    label: "↑" },
  { value: "top-right",     label: "↗" },
  { value: "middle-left",   label: "←" },
  { value: "middle-center", label: "·" },
  { value: "middle-right",  label: "→" },
  { value: "bottom-left",   label: "↙" },
  { value: "bottom-center", label: "↓" },
  { value: "bottom-right",  label: "↘" },
];

export function WatermarkSection({
  watermarkType,
  onWatermarkTypeChange,
  watermarkText,
  onWatermarkTextChange,
  watermarkPosition,
  onWatermarkPositionChange,
  watermarkOpacity,
  onWatermarkOpacityChange,
  watermarkScale,
  onWatermarkScaleChange,
  watermarkFontFamily,
  onWatermarkFontFamilyChange,
  watermarkColor,
  onWatermarkColorChange,
  watermarkImage,
  onWatermarkImageChange,
  uploadedImageUrl,
}: WatermarkSectionProps) {
  return (
    <div className="sectionBody watermarkSection">
      <div className="segmentedField">
        <span>Tipe Watermark</span>
        <div className="segmentedControl" role="group" aria-label="Tipe watermark">
          <button className={watermarkType === "none" ? "active" : ""} type="button" onClick={() => onWatermarkTypeChange("none")}>Tidak Ada</button>
          <button className={watermarkType === "text" ? "active" : ""} type="button" onClick={() => onWatermarkTypeChange("text")}>Teks</button>
          <button className={watermarkType === "image" ? "active" : ""} type="button" onClick={() => onWatermarkTypeChange("image")}>Gambar</button>
        </div>
      </div>

      {watermarkType !== "none" && (
        <>
          <div className="segmentedField">
            <span>Posisi</span>
            <div className="watermarkPositionGrid" role="group" aria-label="Posisi watermark">
              {POSITION_GRID.map((pos) => (
                <button
                  key={pos.value}
                  type="button"
                  className={`watermarkPositionBtn${watermarkPosition === pos.value ? " watermarkPositionBtn--active" : ""}`}
                  aria-label={pos.value}
                  onClick={() => onWatermarkPositionChange(pos.value)}
                >
                  {pos.label}
                </button>
              ))}
            </div>
          </div>

          <div className="segmentedField">
            <span>Opasitas</span>
            <div className="sliderRow">
              <input
                className="fontSlider"
                type="range"
                min={0}
                max={100}
                step={1}
                value={watermarkOpacity}
                onChange={(e) => onWatermarkOpacityChange(Number(e.target.value))}
                aria-label="Opasitas watermark"
              />
              <span className="sliderReadout">{watermarkOpacity}%</span>
            </div>
          </div>

          <div className="segmentedField">
            <span>Skala</span>
            <div className="sliderRow">
              <input
                className="fontSlider"
                type="range"
                min={10}
                max={200}
                step={5}
                value={watermarkScale}
                onChange={(e) => onWatermarkScaleChange(Number(e.target.value))}
                aria-label="Skala watermark"
              />
              <span className="sliderReadout">{watermarkScale}%</span>
            </div>
          </div>
        </>
      )}

      {watermarkType === "text" && (
        <>
          <label className="field">
            <span>Teks Watermark</span>
            <input
              type="text"
              className="textInput"
              value={watermarkText}
              onChange={(e) => onWatermarkTextChange(e.target.value)}
              placeholder="Masukkan teks watermark"
            />
          </label>

          <label className="field">
            <span>Font</span>
            <select
              className="fontSelect"
              value={watermarkFontFamily}
              onChange={(e) => onWatermarkFontFamilyChange(e.target.value)}
            >
              {CAPTION_FONTS.map((font) => (
                <option key={font.value} value={font.value}>{font.label}</option>
              ))}
            </select>
          </label>

          <label className="field captionColorField">
            <span>Warna Teks</span>
            <input
              type="color"
              value={watermarkColor}
              onChange={(e) => onWatermarkColorChange(e.target.value.toUpperCase())}
            />
          </label>
        </>
      )}

      {watermarkType === "image" && (
        <div className="segmentedField">
          <span>File PNG</span>
          <input
            type="file"
            accept="image/png"
            onChange={(e) => onWatermarkImageChange(e.target.files?.[0] ?? null)}
          />
          {watermarkImage && (
            <p className="field-help">File dipilih: {watermarkImage.name}</p>
          )}
          {uploadedImageUrl && !watermarkImage && (
            <p className="field-help">Gambar sudah diunggah.</p>
          )}
        </div>
      )}
    </div>
  );
}
