"use client";

import { CAPTION_FONT_SIZE_MAX, CAPTION_FONT_SIZE_MIN, CAPTION_FONTS } from "../../../lib/constants";
import type { CamCorner, CaptionFont, CaptionPosition, CaptionStyle, CropMode } from "../../../types/clip.type";

type CropCaptionSectionProps = {
  cropMode: CropMode;
  camCorner: CamCorner;
  burnSubtitles: boolean;
  captionFontSize: number;
  captionPosition: CaptionPosition;
  captionColor: string;
  captionFont: CaptionFont;
  captionOutline: number;
  captionOutlineColor: string;
  captionStyle: CaptionStyle;
  onCropModeChange: (mode: CropMode) => void;
  onCamCornerChange: (value: CamCorner) => void;
  onBurnSubtitlesChange: (value: boolean) => void;
  onCaptionFontSizeChange: (value: number) => void;
  onCaptionPositionChange: (value: CaptionPosition) => void;
  onCaptionColorChange: (value: string) => void;
  onCaptionFontChange: (value: CaptionFont) => void;
  onCaptionOutlineChange: (value: number) => void;
  onCaptionOutlineColorChange: (value: string) => void;
  onCaptionStyleChange: (value: CaptionStyle) => void;
};

const CAM_CORNER_OPTIONS: { value: CamCorner; label: string }[] = [
  { value: "auto", label: "Auto" },
  { value: "tl", label: "Kiri Atas" },
  { value: "tr", label: "Kanan Atas" },
  { value: "bl", label: "Kiri Bawah" },
  { value: "br", label: "Kanan Bawah" },
];

const CAPTION_STYLE_OPTIONS: { value: CaptionStyle; label: string; desc: string }[] = [
  { value: "classic", label: "Classic", desc: "Putih + outline" },
  { value: "bold", label: "Bold", desc: "Outline tebal" },
  { value: "boxed", label: "Boxed", desc: "Kotak gelap" },
  { value: "highlight", label: "Highlight", desc: "Box semi-transparan" },
  { value: "shadow", label: "Shadow", desc: "Bayangan lembut" },
];

export function CropCaptionSection({
  cropMode,
  camCorner,
  burnSubtitles,
  captionFontSize,
  captionPosition,
  captionColor,
  captionFont,
  captionOutline,
  captionOutlineColor,
  captionStyle,
  onCropModeChange,
  onCamCornerChange,
  onBurnSubtitlesChange,
  onCaptionFontSizeChange,
  onCaptionPositionChange,
  onCaptionColorChange,
  onCaptionFontChange,
  onCaptionOutlineChange,
  onCaptionOutlineColorChange,
  onCaptionStyleChange,
}: CropCaptionSectionProps) {
  return (
    <div className="sectionBody">
      <div className="segmentedField">
        <span>Mode Crop</span>
        <div className="segmentedControl" role="group" aria-label="Mode crop video">
          <button className={cropMode === "center" ? "active" : ""} type="button" onClick={() => onCropModeChange("center")}>Center</button>
          <button className={cropMode === "person" ? "active" : ""} type="button" onClick={() => onCropModeChange("person")}>Follow Person</button>
          <button className={cropMode === "streamer" ? "active" : ""} type="button" onClick={() => onCropModeChange("streamer")}>Streamer</button>
          <button className={cropMode === "pillarbox" ? "active" : ""} type="button" onClick={() => onCropModeChange("pillarbox")}>Pillarbox</button>
          <button className={cropMode === "split" ? "active" : ""} type="button" onClick={() => onCropModeChange("split")}>Split Screen</button>
        </div>
      </div>

      {cropMode === "split" ? (
        <p className="field-help">Layar terbagi dua: wajah mengikuti orang di panel atas, kegiatan penuh di panel bawah (vertikal 9:16).</p>
      ) : null}

      {cropMode === "streamer" ? (
        <div className="segmentedField">
          <span>Posisi Webcam di Sumber</span>
          <div className="segmentedControl segmentedControl--grid" role="group" aria-label="Posisi webcam">
            {CAM_CORNER_OPTIONS.map((option) => (
              <button key={option.value} className={camCorner === option.value ? "active" : ""} type="button" onClick={() => onCamCornerChange(option.value)}>
                {option.label}
              </button>
            ))}
          </div>
          <p className="field-help">Webcam di-crop dari pojok ini lalu ditumpuk di atas gameplay (vertikal 9:16).</p>
        </div>
      ) : null}

      <div className="aiBlock">
        <label className="aiToggle">
          <span className="aiToggleLabel">Tempel Subtitle</span>
          <input type="checkbox" checked={burnSubtitles} onChange={(event) => onBurnSubtitlesChange(event.target.checked)} aria-label="Tempel Subtitle" />
        </label>
        <p className="field-help">Tempelkan teks transkrip langsung ke dalam video.</p>

        {burnSubtitles ? (
          <div className="captionFields">
            <div className="captionControls">
              <div className="segmentedField">
                <span>Style Caption</span>
                <div className="captionStylePicker">
                  {CAPTION_STYLE_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      className={`captionStyleChip${captionStyle === opt.value ? " captionStyleChip--active" : ""}`}
                      onClick={() => onCaptionStyleChange(opt.value)}
                      title={opt.desc}
                    >
                      <span className={`captionStylePreview captionStylePreview--${opt.value}`}>Aa</span>
                      <span className="captionStyleLabel">{opt.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="segmentedField">
                <span>Ukuran Font</span>
                <div className="sliderRow">
                  <input className="fontSlider" type="range" min={CAPTION_FONT_SIZE_MIN} max={CAPTION_FONT_SIZE_MAX} step={1} value={captionFontSize} onChange={(event) => onCaptionFontSizeChange(Number(event.target.value))} aria-label="Ukuran font caption" />
                  <span className="sliderReadout">{captionFontSize}px</span>
                </div>
                <div className="sliderTicks"><span>Kecil</span><span>Sedang</span><span>Besar</span></div>
              </div>

              <div className="segmentedField">
                <span>Posisi</span>
                <div className="segmentedControl" role="group" aria-label="Posisi caption">
                  <button className={captionPosition === "center" ? "active" : ""} type="button" onClick={() => onCaptionPositionChange("center")}>Tengah</button>
                  <button className={captionPosition === "bottom" ? "active" : ""} type="button" onClick={() => onCaptionPositionChange("bottom")}>Bawah</button>
                </div>
              </div>

              <label className="field">
                <span>Jenis Font</span>
                <select className="fontSelect" value={captionFont} onChange={(event) => onCaptionFontChange(event.target.value as CaptionFont)}>
                  {CAPTION_FONTS.map((font) => (
                    <option key={font.value} value={font.value}>{font.label}</option>
                  ))}
                </select>
              </label>

              <div className="captionColorRow">
                <label className="field captionColorField">
                  <span>Warna Teks</span>
                  <input type="color" value={captionColor} onChange={(event) => onCaptionColorChange(event.target.value.toUpperCase())} />
                </label>
                <label className="field captionColorField">
                  <span>Warna Border</span>
                  <input type="color" value={captionOutlineColor} onChange={(event) => onCaptionOutlineColorChange(event.target.value.toUpperCase())} />
                </label>
              </div>

              <div className="segmentedField">
                <span>Tebal Border</span>
                <div className="sliderRow">
                  <input className="fontSlider" type="range" min={0} max={8} step={0.5} value={captionOutline} onChange={(event) => onCaptionOutlineChange(Number(event.target.value))} aria-label="Tebal border caption" />
                  <span className="sliderReadout">{captionOutline}px</span>
                </div>
                <div className="sliderTicks"><span>Tanpa</span><span>Tebal</span></div>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
