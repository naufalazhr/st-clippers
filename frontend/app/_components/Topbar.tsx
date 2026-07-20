import { RefreshCw } from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";

type TopbarProps = {
  onRefresh: () => void;
};

export function Topbar({ onRefresh }: TopbarProps) {
  return (
    <nav className="floatingNav">
      <div className="floatingNav-brand">
        <h1 className="wordmark">Sultan Clip</h1>
      </div>
      <div className="floatingNav-actions">
        <ThemeToggle />
        <button className="iconButton" type="button" onClick={onRefresh} title="Refresh data">
          <RefreshCw size={18} />
        </button>
      </div>
    </nav>
  );
}
