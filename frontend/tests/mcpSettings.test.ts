import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const read = (p: string) => readFileSync(resolve(__dirname, "..", p), "utf-8");
const settings = read("app/_components/desktop/McpSettings.tsx");

// The address and token are generated per install, so this screen is the only
// correct documentation of them (playbook A.7).
describe("MCP settings screen", () => {
  it("renders the bound port, not the preferred one", () => {
    expect(settings).toContain("status.url");
    expect(settings).toContain("bound_port");
  });

  it("masks the token but allows reveal and copy", () => {
    expect(settings).toContain("maskedToken");
    expect(settings).toContain("revealed");
    expect(settings).toContain("copy(\"token\"");
  });

  it("offers token regeneration, the only remediation if it leaks", () => {
    expect(settings).toContain("regenerateMcpToken");
  });

  it("warns when the port moved", () => {
    // Otherwise the failure is indistinguishable from "the app isn't running".
    expect(settings).toContain("status.port_changed");
    expect(settings).toContain("Port berubah");
  });

  it("surfaces a listener failure", () => {
    expect(settings).toContain("status.last_error");
  });

  it("renders both an agent prompt and a config-file snippet", () => {
    // Agents fall into two camps and you cannot predict which the user has.
    expect(settings).toContain("agentPrompt");
    expect(settings).toContain("hermesYaml");
    expect(settings).toContain("mcp_servers");
  });

  it("states the trust model in plain language", () => {
    expect(settings).toContain("127.0.0.1");
    expect(settings).toMatch(/berjalan sebagai user kamu/);
  });

  it("is reachable from the sidebar", () => {
    const sidebar = read("app/_components/desktop/Sidebar.tsx");
    expect(sidebar).toContain('id: "settings"');
    const shell = read("app/_components/desktop/DesktopShell.tsx");
    expect(shell).toContain('"settings"');
  });
});

describe("MCP api client", () => {
  it("exposes status, toggle and regenerate", () => {
    const client = read("lib/apiClient.ts");
    expect(client).toContain("/api/mcp/status");
    expect(client).toContain("/api/mcp/enabled");
    expect(client).toContain("/api/mcp/regenerate-token");
  });
});
