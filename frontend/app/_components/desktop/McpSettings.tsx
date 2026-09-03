"use client";

import { AlertTriangle, Check, Copy, Eye, EyeOff, Plug, RefreshCw, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import toast from "react-hot-toast";
import { getMcpStatus, regenerateMcpToken, setMcpEnabled, type McpStatus } from "../../../lib/apiClient";
import "./McpSettings.css";

/**
 * The address and token are generated per install, so nothing written down
 * elsewhere can be correct about them. This screen is the source of truth: it
 * renders the port actually bound and the token actually in use.
 */
export function McpSettings() {
  const [status, setStatus] = useState<McpStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setStatus(await getMcpStatus());
    } catch {
      // The backend may still be starting; the retry below covers it.
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const copy = useCallback(async (label: string, value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(label);
      setTimeout(() => setCopied((c) => (c === label ? null : c)), 1600);
    } catch {
      toast.error("Gagal menyalin");
    }
  }, []);

  const toggle = useCallback(async () => {
    if (!status) return;
    setBusy(true);
    try {
      setStatus(await setMcpEnabled(!status.enabled));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Gagal mengubah status MCP");
    } finally {
      setBusy(false);
    }
  }, [status]);

  const regenerate = useCallback(async () => {
    setBusy(true);
    try {
      setStatus(await regenerateMcpToken());
      toast.success("Token baru dibuat. Perbarui konfigurasi agent kamu.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Gagal membuat token baru");
    } finally {
      setBusy(false);
    }
  }, []);

  if (!status) {
    return (
      <section className="mcpSettings">
        <div className="mcpSettings-loading">Memuat status MCP...</div>
      </section>
    );
  }

  const url = status.url ?? `http://127.0.0.1:${status.preferred_port}/mcp`;
  const maskedToken = status.token ? `${status.token.slice(0, 6)}${"•".repeat(24)}` : "";

  const agentPrompt =
    `Add an MCP server named "sultan-clip" at ${url} using Streamable HTTP transport, ` +
    `with the header "Authorization: Bearer ${status.token}". It runs locally on this ` +
    `machine. Once connected, list its tools and tell me what you can do.`;

  const hermesYaml = `# ~/.hermes/config.yaml
mcp_servers:
  sultan_clip:
    url: "${url}"
    headers:
      Authorization: "Bearer ${status.token}"`;

  return (
    <section className="mcpSettings">
      <header className="mcpSettings-header">
        <div>
          <h2>Akses Agent (MCP)</h2>
          <p className="mcpSettings-sub">
            Izinkan asisten AI seperti Hermes menjalankan Sultan Clip dari Telegram.
          </p>
        </div>
        <button
          className={`mcpToggle${status.enabled ? " is-on" : ""}`}
          onClick={toggle}
          disabled={busy}
          role="switch"
          aria-checked={status.enabled}
        >
          <span className="mcpToggle-track"><span className="mcpToggle-thumb" /></span>
          {status.enabled ? "Aktif" : "Nonaktif"}
        </button>
      </header>

      <div className="mcpStatusRow">
        <span className={`mcpDot mcpDot--${status.running ? "on" : "off"}`} />
        {status.running
          ? `Berjalan di port ${status.bound_port}`
          : status.enabled
            ? "Aktif tapi tidak berjalan"
            : "Tidak berjalan"}
      </div>

      {status.port_changed && (
        <div className="mcpNotice mcpNotice--warn">
          <AlertTriangle size={16} />
          <div>
            <strong>Port berubah ke {status.bound_port}.</strong> Port sebelumnya
            dipakai aplikasi lain. Konfigurasi agent yang dibuat sebelumnya kini
            menunjuk ke alamat kosong — salin ulang URL di bawah, lalu restart agent-nya.
          </div>
        </div>
      )}

      {status.last_error && (
        <div className="mcpNotice mcpNotice--error">
          <AlertTriangle size={16} />
          <div><strong>Gagal menjalankan server:</strong> {status.last_error}</div>
        </div>
      )}

      {status.enabled && (
        <>
          <div className="mcpField">
            <label>Alamat server</label>
            <div className="mcpField-row">
              <code>{url}</code>
              <button onClick={() => copy("url", url)} title="Salin URL">
                {copied === "url" ? <Check size={15} /> : <Copy size={15} />}
              </button>
            </div>
          </div>

          <div className="mcpField">
            <label>Token</label>
            <div className="mcpField-row">
              <code className="mcpToken">{revealed ? status.token : maskedToken}</code>
              <button onClick={() => setRevealed((v) => !v)} title={revealed ? "Sembunyikan" : "Tampilkan"}>
                {revealed ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
              <button onClick={() => copy("token", status.token)} title="Salin token">
                {copied === "token" ? <Check size={15} /> : <Copy size={15} />}
              </button>
              <button onClick={regenerate} disabled={busy} title="Buat token baru">
                <RefreshCw size={15} />
              </button>
            </div>
            <small>Membuat token baru akan memutus agent yang masih memakai token lama.</small>
          </div>

          <div className="mcpField">
            <label>
              <Plug size={13} /> Untuk agent yang diatur lewat percakapan
            </label>
            <div className="mcpField-row mcpField-row--block">
              <pre>{agentPrompt}</pre>
              <button onClick={() => copy("prompt", agentPrompt)} title="Salin">
                {copied === "prompt" ? <Check size={15} /> : <Copy size={15} />}
              </button>
            </div>
          </div>

          <div className="mcpField">
            <label>Untuk Hermes (file konfigurasi)</label>
            <div className="mcpField-row mcpField-row--block">
              <pre>{hermesYaml}</pre>
              <button onClick={() => copy("yaml", hermesYaml)} title="Salin">
                {copied === "yaml" ? <Check size={15} /> : <Copy size={15} />}
              </button>
            </div>
            <small>Restart Hermes setelah mengubah konfigurasinya.</small>
          </div>
        </>
      )}

      <div className="mcpNotice mcpNotice--trust">
        <ShieldCheck size={16} />
        <div>
          Server hanya mendengarkan di <code>127.0.0.1</code>, jadi tidak bisa
          dijangkau dari luar komputer ini. Namun <strong>semua program yang
          berjalan sebagai user kamu bisa membaca token</strong> dan memakai
          tool-nya — termasuk memakai kuota AI kamu. MCP mati secara default dan
          bisa dimatikan kapan saja di sini.
        </div>
      </div>
    </section>
  );
}
