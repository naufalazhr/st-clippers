"use client";

type HashtagsSectionProps = {
  requiredHashtags: string;
  onRequiredHashtagsChange: (value: string) => void;
};

export function HashtagsSection({
  requiredHashtags,
  onRequiredHashtagsChange,
}: HashtagsSectionProps) {
  return (
    <div className="sectionBody">
      <label className="field wide">
        <span>Hashtag Wajib (opsional)</span>
        <input
          value={requiredHashtags}
          onChange={(event) => onRequiredHashtagsChange(event.target.value)}
          placeholder="sultanclip, viral, fyp"
        />
        <p className="field-help">
          Hashtag ini selalu ditambahkan ke caption yang digenerate. Pisahkan dengan koma.
        </p>
      </label>
    </div>
  );
}
