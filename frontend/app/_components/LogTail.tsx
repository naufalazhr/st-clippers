import { useEffect, useRef } from "react";

type LogTailProps = {
  logs: string[];
};

export function LogTail({ logs }: LogTailProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [logs]);

  return (
    <div className="logBox" ref={ref}>
      {logs.length ? (
        logs.map((line, index) => <p key={`${line}-${index}`}>{line}</p>)
      ) : (
        <p>Memulai proses pipeline...</p>
      )}
    </div>
  );
}
