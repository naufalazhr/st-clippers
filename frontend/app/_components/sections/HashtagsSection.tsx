"use client";

import { useState, type KeyboardEvent } from "react";

type HashtagsSectionProps = {
  requiredHashtags: string[];
  onRequiredHashtagsChange: (tags: string[]) => void;
};

export function HashtagsSection({
  requiredHashtags,
  onRequiredHashtagsChange,
}: HashtagsSectionProps) {
  const [input, setInput] = useState("");

  function addTag(raw: string) {
    const tag = raw.trim().replace(/^#/, "");
    if (tag && !requiredHashtags.includes(tag)) {
      onRequiredHashtagsChange([...requiredHashtags, tag]);
    }
    setInput("");
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addTag(input);
    } else if (e.key === "Backspace" && input === "" && requiredHashtags.length > 0) {
      onRequiredHashtagsChange(requiredHashtags.slice(0, -1));
    }
  }

  function handleBlur() {
    if (input.trim()) addTag(input);
  }

  function removeTag(tag: string) {
    onRequiredHashtagsChange(requiredHashtags.filter((t) => t !== tag));
  }

  return (
    <div className="sectionBody">
      <label className="field wide">
        <span>Hashtag Wajib (opsional)</span>
        <div className="chipField">
          {requiredHashtags.length > 0 && (
            <div className="chipList">
              {requiredHashtags.map((tag) => (
                <span key={tag} className="chip">
                  #{tag}
                  <button
                    type="button"
                    className="chipRemove"
                    onClick={() => removeTag(tag)}
                    aria-label={`Hapus #${tag}`}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
          <input
            className="chipInput"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            onBlur={handleBlur}
            placeholder={requiredHashtags.length === 0 ? "sultanclip, viral, fyp" : "Tambah hashtag..."}
          />
        </div>
        <p className="field-help">
          Ketik hashtag lalu tekan Enter atau koma. Hashtag ini selalu ditambahkan ke caption.
        </p>
      </label>
    </div>
  );
}
