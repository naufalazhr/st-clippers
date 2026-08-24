"use client";

type RangeSectionProps = {
  maxDuration: number;
  minDuration: number;
  targetClips: number;
  maxClips: number | null;
  videoDuration: number | null;
  onTargetClipsChange: (value: number) => void;
  onMaxDurationChange: (value: number) => void;
  onMinDurationChange: (value: number) => void;
};

export function RangeSection({
  maxDuration,
  minDuration,
  targetClips,
  maxClips,
  videoDuration,
  onTargetClipsChange,
  onMaxDurationChange,
  onMinDurationChange,
}: RangeSectionProps) {
  return (
    <div className="sectionBody">
      <label className="field wide">
        <span>Target Jumlah Clip</span>
        <input
          min={0}
          max={maxClips ?? 50}
          type="number"
          value={targetClips || ""}
          placeholder="Auto (kosongkan = otomatis)"
          aria-label="Target jumlah clip"
          onChange={(event) => onTargetClipsChange(Math.max(0, Number(event.target.value)))}
        />
        <p className="field-help">
          {videoDuration
            ? `Durasi video ~${Math.round(videoDuration)}s. Maks ${maxClips} clip (durasi min × jumlah ≤ 80% video).`
            : "Kosongkan untuk otomatis. Akan disesuaikan dengan panjang video."}
          {maxClips !== null && targetClips > maxClips
            ? ` Target ${targetClips} melebihi batas, akan dipangkas ke ${maxClips}.`
            : ""}
        </p>
      </label>

      <div className="gridFields">
        <label className="field">
          <span>Durasi Minimum</span>
          <input
            min={5}
            max={600}
            type="number"
            value={minDuration}
            onChange={(event) => onMinDurationChange(Number(event.target.value))}
          />
        </label>
        <label className="field">
          <span>Durasi Maksimum</span>
          <input
            min={10}
            max={600}
            type="number"
            value={maxDuration}
            onChange={(event) => onMaxDurationChange(Number(event.target.value))}
          />
        </label>
      </div>
    </div>
  );
}
