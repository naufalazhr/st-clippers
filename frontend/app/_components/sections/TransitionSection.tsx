"use client";

import type { Transition } from "../../../types/clip.type";

type TransitionSectionProps = {
  transition: Transition;
  onTransitionChange: (value: Transition) => void;
};

const TRANSITION_OPTIONS: { value: Transition; label: string; icon: string }[] = [
  { value: "none", label: "Tanpa Efek", icon: "—" },
  { value: "fade", label: "Fade", icon: "◐" },
  { value: "fadeblack", label: "Fade Hitam", icon: "●" },
  { value: "fadewhite", label: "Fade Putih", icon: "○" },
];

export function TransitionSection({ transition, onTransitionChange }: TransitionSectionProps) {
  return (
    <div className="sectionBody">
      <div className="segmentedField">
        <span>Efek Transisi</span>
        <div className="transitionPicker">
          {TRANSITION_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              className={`transitionChip${transition === opt.value ? " transitionChip--active" : ""}`}
              onClick={() => onTransitionChange(opt.value)}
            >
              <span className="transitionIcon">{opt.icon}</span>
              {opt.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
