import { RefreshCw } from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";

type TopbarProps = {
  onRefresh: () => void;
};

export function Topbar({ onRefresh }: TopbarProps) {
  return (
    <section className="topbar">
      <div className="topbar-brand">
        <div className="brandCopy">
          <h1 className="logo-text wordmark">Sultan Clip</h1>
          <p className="tagline">Turn long videos into ready-to-post clips.</p>
        </div>
      </div>
      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <ThemeToggle />
        <button className="iconButton" type="button" onClick={onRefresh} title="Refresh data">
          <RefreshCw size={18} />
        </button>
      </div>
    </section>
  );
}
