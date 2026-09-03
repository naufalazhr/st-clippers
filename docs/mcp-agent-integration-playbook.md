# MCP + Telegram Agent Integration — Portable Playbook

> A reference for reproducing the Flomeria Desktop MCP integration in **another
> desktop app**, and for driving that app from **Hermes over Telegram**.
>
> Status: reference document, written 2026-09-03 against the shipped
> implementation in this repo (`src-tauri/src/mcp/`, `src/lib/mcp/`).
> For the design history of *this* app's integration see
> [`hermes-mcp-integration.md`](./hermes-mcp-integration.md) — that document is
> the decision record; this one is the how-to.

---

## 0. How to read this

Every code block is taken from working code in this repo, with the
Flomeria-specific parts marked `<<YOUR APP>>`. Sections are ordered as a build
sequence: each part ends in something you can verify before starting the next.
Skipping the verification steps is how a stuck bridge gets mistaken for a
protocol bug three layers later.

**Assumed stack for Part A:** Tauri v2 (Rust shell + web frontend). Section
[A.8](#a8-if-your-app-is-not-tauri) covers what changes for Electron or a
native app.

**Assumed for Part C:** Hermes Agent is MCP-native and configured by a YAML
file. Where a detail of Hermes is not knowable from here it is marked
**〔verify〕** rather than guessed.

---

## 1. What you are building

Three planes. The middle one is your app; the other two are things you connect
to it.

```
  ┌── AGENT SURFACE ───────────────────────────────────────────┐
  │  Telegram  ◄──── long polling ────►  Hermes Agent           │
  │  (phone)                             (~/.hermes/config.yaml)│
  └───────────────────────────┬────────────────────────────────┘
                              │  MCP · Streamable HTTP
                              │  POST http://127.0.0.1:<port>/mcp
                              │  Authorization: Bearer <per-install token>
  ┌───────────────────────────▼────────────────────────────────┐
  │  YOUR DESKTOP APP (tray-resident)                          │
  │                                                             │
  │   Rust process                    WebView (TypeScript)      │
  │   ─────────────                   ────────────────────      │
  │   mcp/server.rs   axum listener                             │
  │     · bearer auth                                           │
  │     · initialize / ping  ── answered in Rust                │
  │     · tools/list, tools/call ──emit──►  mcp/bridge.ts       │
  │   mcp/bridge.rs   oneshot channel  ◄──invoke──  mcp/tools.ts│
  │                                            │                │
  │   tray.rs  (close → hide, not quit)        ▼                │
  │                                     your domain logic       │
  └───────────────────────────┬────────────────────────────────┘
                              │
                  ┌───────────▼───────────┐
                  │  DATA / PROVIDERS      │
                  │  DB, APIs, disk, keys  │
                  └────────────────────────┘
```

**The one structural decision everything else follows from:** Rust owns the
socket and the authentication; **the tool handlers run in the webview**, where
your session, your credentials and your business logic already are. Rust never
sees a key. Reimplementing the domain layer in Rust to keep it "all native"
means maintaining it twice.

---

## 2. Decisions worth copying

These are the choices that turned out to matter. Each cost us a bug before it
was made deliberately.

| Decision | Why | Section |
|---|---|---|
| Handlers in the webview, socket in Rust | Domain logic, auth session and secrets already live there | [A.4](#a4-the-bridge) |
| **Stateless** Streamable HTTP, no SSE | One `POST` per JSON-RPC message is dramatically simpler; long-poll tools replace progress notifications | [A.3](#a3-the-http-listener) |
| Per-install random bearer token | There is then no shareable config to leak or to document wrongly | [A.2](#a2-token-and-config) |
| Port is **discovered and persisted**, never assumed | Agent configs are static files; a port that moves every launch breaks them silently | [A.3](#a3-the-http-listener) |
| Close hides the window; quit is on the tray | The webview must be alive to serve a tool call | [A.6](#a6-app-lifecycle) |
| Settings screen renders **live** address + token | No documentation can ever be correct for a per-install value | [A.7](#a7-the-settings-screen) |
| Every dispatch replies **exactly once** | A silent handler strands the agent until the bridge timeout — which reads as a hang, not a failure | [A.4](#a4-the-bridge) |
| Tools return **shape, not recipe** | Inspection tools expose structure; only explicit, owner-gated export tools return authored content | [B.3](#b3-what-a-tool-must-never-return) |
| Long-poll with a hard cap under the bridge timeout | The agent gets an answer or a run id, never a hung socket | [B.4](#b4-the-long-poll-contract) |
| Run registry outside the UI framework | A run must outlive the request that started it, and the React tree that rendered it | [B.5](#b5-the-run-registry) |

---

# Part A — The MCP server inside the app

## A.1 Dependencies

```toml
# src-tauri/Cargo.toml
[dependencies]
tauri = { version = "2", features = ["tray-icon", "image-png"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"

# Localhost MCP server (Streamable HTTP). Rust owns the socket and the bearer
# check only; every tool handler runs in the webview.
tokio = { version = "1", features = ["sync", "time", "macros", "net"] }
axum = "0.8"
uuid = { version = "1", features = ["v4"] }
rand = "0.8"
subtle = "2"        # constant-time token comparison
```

`subtle` is not optional decoration — see [A.2](#a2-token-and-config).

File layout to create:

```
src-tauri/src/mcp/
  mod.rs        state, Tauri commands, status struct
  auth.rs       token generation/persistence, bearer check, config file
  server.rs     axum listener, port fallback, JSON-RPC dispatch
  bridge.rs     Rust → webview call, oneshot channel
src/lib/mcp/
  bridge.ts     webview → Rust reply
  tools.ts      tool schemas + handlers + dispatchMcp
```

## A.2 Token and config

Two files under `app_config_dir()`: `mcp-token` (the secret) and `mcp.json`
(`{enabled, port}`).

```rust
// src-tauri/src/mcp/auth.rs
pub fn get_or_create_token(app: &AppHandle) -> Result<String, String> {
    let path = token_path(app)?;
    if let Ok(existing) = fs::read_to_string(&path) {
        let trimmed = existing.trim().to_string();
        if !trimmed.is_empty() {
            return Ok(trimmed);
        }
    }
    write_new_token(&path)
}

fn write_new_token(path: &PathBuf) -> Result<String, String> {
    use rand::RngCore;
    let mut bytes = [0u8; 32];
    rand::thread_rng().fill_bytes(&mut bytes);
    let token = hex_encode(&bytes);
    fs::write(path, &token).map_err(|e| e.to_string())?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = fs::set_permissions(path, fs::Permissions::from_mode(0o600));
    }
    Ok(token)
}

/// Constant-time so a wrong token cannot be discovered one byte at a time by
/// timing the responses.
pub fn check_bearer(expected_token: &str, authorization_header: Option<&str>) -> bool {
    let Some(header) = authorization_header else { return false };
    let Some(presented) = header.strip_prefix("Bearer ") else { return false };
    presented.as_bytes().ct_eq(expected_token.as_bytes()).into()
}
```

Unit-test the check before anything else — it is pure, and it is the only thing
standing between a local process and your tools:

```rust
#[test]
fn rejects_missing_and_malformed_headers() {
    assert!(!check_bearer("abc", None));
    assert!(!check_bearer("abc", Some("abc")));       // no scheme
    assert!(!check_bearer("abc", Some("Basic abc")));
    assert!(!check_bearer("abc", Some("bearer abc"))); // case matters
}

#[test]
fn accepts_only_the_exact_token() {
    assert!(check_bearer("abc", Some("Bearer abc")));
    assert!(!check_bearer("abc", Some("Bearer abcd")));  // prefix is not enough
    assert!(!check_bearer("abc", Some("Bearer ab")));
}
```

> **Rule:** never log the token, never put it in a URL query string, never bake
> it into a documented example. The MCP authorization spec requires the token
> in the `Authorization` header on **every** request, not just the handshake.

## A.3 The HTTP listener

### Port selection

```rust
// src-tauri/src/mcp/server.rs
const PORT_SCAN_RANGE: u16 = 20;

async fn bind_with_fallback(preferred: u16) -> Result<(TcpListener, u16), String> {
    let mut last_err = String::new();

    for candidate in preferred..preferred.saturating_add(PORT_SCAN_RANGE) {
        match TcpListener::bind(("127.0.0.1", candidate)).await {
            Ok(listener) => return Ok((listener, candidate)),
            Err(e) => last_err = e.to_string(),
        }
    }

    // Port 0 asks the OS for any free port. A working server on an odd port
    // (which the UI reports) beats no server at all.
    match TcpListener::bind(("127.0.0.1", 0)).await {
        Ok(listener) => {
            let port = listener.local_addr().map_err(|e| format!("local_addr: {e}"))?.port();
            Ok((listener, port))
        }
        Err(e) => Err(format!(
            "could not bind any port on 127.0.0.1 starting at {preferred}: {last_err}; {e}"
        )),
    }
}
```

Then — and this is the part people skip — **persist what you actually bound and
prefer it next launch**, and raise a flag when it moved:

```rust
{
    let state = app.state::<McpState>();
    *state.bound_port.lock().unwrap() = Some(bound);
    *state.port_changed.lock().unwrap() = bound != preferred;
    *state.preferred_port.lock().unwrap() = bound;   // sticky
}
let _ = auth::save_config(&app, auth::McpConfig { enabled: true, port: bound });
```

`port_changed` exists for one reason: when the port moves, an agent config
written earlier now points at nothing, and the failure is
**indistinguishable from "the app isn't running"**. The settings screen must
say so out loud.

Bind `127.0.0.1`, never `0.0.0.0`. The loopback bind *is* the network boundary
of this design.

### JSON-RPC dispatch

```rust
const SUPPORTED_PROTOCOL_VERSIONS: [&str; 3] = ["2025-06-18", "2025-03-26", "2024-11-05"];
const FALLBACK_PROTOCOL_VERSION: &str = "2025-03-26";

async fn handle_mcp(State(ctx): State<ServerCtx>, headers: HeaderMap, body: Bytes) -> Response {
    let authorization = headers.get("authorization").and_then(|v| v.to_str().ok());
    if !auth::check_bearer(&ctx.token, authorization) {
        return (StatusCode::UNAUTHORIZED, "unauthorized").into_response();
    }

    let message: Value = match serde_json::from_slice(&body) {
        Ok(v) => v,
        Err(_) => return rpc_error(Value::Null, -32700, "parse error"),
    };

    // Notifications (no id) are acknowledged and dropped.
    let Some(id) = message.get("id").cloned() else {
        return StatusCode::ACCEPTED.into_response();
    };
    let method = message.get("method").and_then(|m| m.as_str()).unwrap_or("");
    let params = message.get("params").cloned().unwrap_or(json!({}));

    match method {
        "initialize" => { /* echo a supported protocolVersion, advertise {"tools":{}} */ }
        "ping" => rpc_result(id, json!({})),
        "tools/list" | "tools/call" => match bridge::call_webview(&ctx.app, method, params).await {
            Ok(reply) => { /* {ok} → result, {error} → JSON-RPC error */ }
            Err(bridge::BridgeError::Timeout) => rpc_error(
                id, -32000,
                "App did not respond - the window may be closed or a handler is stuck",
            ),
            Err(bridge::BridgeError::Emit(e)) => rpc_error(id, -32000, &e),
        },
        _ => rpc_error(id, -32601, "method not found"),
    }
}
```

Four details that are load-bearing:

1. **Auth before parse.** An unauthenticated caller learns nothing about your
   payload handling.
2. **Notifications get `202 Accepted` and nothing else.** `notifications/initialized`
   arrives right after the handshake; answering it with a JSON-RPC response is a
   protocol error some clients reject.
3. **Echo the client's `protocolVersion` if you support it**, otherwise return
   your fallback. Keep `SUPPORTED_PROTOCOL_VERSIONS` current — the spec has
   moved since this list was written (`2025-11-25` exists now); add versions as
   you verify them.
4. **Only `POST /mcp` is routed.** A `GET` therefore returns 405, which is
   exactly what the spec says a server without SSE support should do. Do not
   add a GET route that returns 200 with an empty body — clients read that as a
   broken stream.

## A.4 The bridge

Rust emits an event and waits on a oneshot channel keyed by a UUID.

```rust
// src-tauri/src/mcp/bridge.rs
pub const BRIDGE_TIMEOUT: Duration = Duration::from_secs(150);

#[derive(Default)]
pub struct McpBridge {
    pending: Mutex<HashMap<String, oneshot::Sender<Value>>>,
}

pub async fn call_webview(app: &AppHandle, method: &str, params: Value)
    -> Result<Value, BridgeError>
{
    let id = uuid::Uuid::new_v4().to_string();
    let (tx, rx) = oneshot::channel();
    app.state::<McpBridge>().pending.lock().unwrap().insert(id.clone(), tx);

    if let Err(e) = app.emit_to("main", "mcp://tool-call",
        json!({ "id": id, "method": method, "params": params }))
    {
        app.state::<McpBridge>().pending.lock().unwrap().remove(&id);
        return Err(BridgeError::Emit(e.to_string()));
    }

    match tokio::time::timeout(BRIDGE_TIMEOUT, rx).await {
        Ok(Ok(value)) => Ok(value),
        _ => {
            // Always clean up the pending entry, or a wedged handler leaks a
            // sender for the life of the process.
            app.state::<McpBridge>().pending.lock().unwrap().remove(&id);
            Err(BridgeError::Timeout)
        }
    }
}

#[tauri::command]
pub fn mcp_tool_result(bridge: tauri::State<'_, McpBridge>, id: String, result: Value) {
    if let Some(tx) = bridge.pending.lock().unwrap().remove(&id) {
        let _ = tx.send(result);
    }
}
```

The webview half:

```ts
// src/lib/mcp/bridge.ts
export async function startMcpBridge(): Promise<void> {
  if (started || !isTauri) return;          // idempotent; no-op in a browser
  started = true;

  const { listen } = await import('@tauri-apps/api/event');
  const { invoke } = await import('@tauri-apps/api/core');

  unlisten = await listen<ToolCallEvent>('mcp://tool-call', (event) => {
    const { id, method, params } = event.payload ?? ({} as ToolCallEvent);
    if (!id) return;

    // Deliberately not awaited: each call runs independently so a slow tool
    // cannot block the event loop for the next one.
    void (async () => {
      let result: unknown;
      try {
        result = await dispatchMcp(method, params);
      } catch (err) {
        // dispatchMcp is written not to throw; this is the belt-and-braces
        // path that guarantees the Rust side always gets its one reply.
        result = { error: { code: -32603, message: String(err) } };
      }
      await invoke('mcp_tool_result', { id, result });
    })();
  });
}
```

Start it once, at app boot, above your React tree — **not** inside a component:

```ts
// src/main.tsx
import { startMcpBridge } from './lib/mcp/bridge';
void startMcpBridge();
```

> **The timeout budget is a contract.** Bridge timeout 150 s → tool long-poll
> cap 120 s → a comfortable margin for the handler's own teardown. Pick your
> numbers once, write them in both files, and derive the tool cap from the
> bridge value rather than choosing it separately.

### Why a bridge at all

Because the alternative is worse in a specific way: your domain logic needs an
authenticated session, provider credentials, and (in our case) code that must
stay byte-for-byte mirrored with a server-side copy. Moving that into Rust to
avoid one event hop means maintaining two implementations that must agree
forever. The hop costs microseconds; the duplication costs every future bug
twice.

## A.5 The tool registry

One module owns schemas, handlers and the dispatcher. The reply contract is the
whole interface with Rust:

```ts
// src/lib/mcp/tools.ts
export interface McpReplyOk { ok: unknown }
export interface McpReplyError { error: { code: number; message: string } }
export type McpReply = McpReplyOk | McpReplyError;

const INVALID_PARAMS = -32602;   // bad arguments
const TOOL_FAILED    = -32000;   // handler-level failure

const fail = (code: number, message: string): McpReplyError => ({ error: { code, message } });

export const TOOL_DEFINITIONS = [
  {
    name: 'do_the_thing',
    description: '...',                       // see B.2 — this is prompt, not prose
    inputSchema: {
      type: 'object',
      properties: { /* ... */ },
      required: ['...'],
      additionalProperties: false,            // always: it turns typos into errors
    },
  },
];

const HANDLERS: Record<string, (args: Record<string, any>) => Promise<McpReply>> = {
  do_the_thing: handleDoTheThing,
};

export async function dispatchMcp(method: string, params: unknown): Promise<McpReply> {
  try {
    if (method === 'tools/list') return { ok: { tools: TOOL_DEFINITIONS } };
    if (method === 'tools/call') {
      const { name, arguments: args } = (params ?? {}) as any;
      const handler = HANDLERS[name];
      if (!handler) return fail(INVALID_PARAMS, `unknown tool: ${name}`);
      return await handler(args ?? {});
    }
    return fail(-32601, `unsupported method: ${method}`);
  } catch (err) {
    return fail(-32603, errMessage(err));     // nothing escapes
  }
}
```

Two hard-won details:

**Errors are not always `Error`.** A Postgres/PostgREST client throws plain
`{message}` objects; `String(e)` on one yields `"[object Object]"`. Have one
helper and use it everywhere:

```ts
const errMessage = (err: unknown): string =>
  err instanceof Error ? err.message : ((err as { message?: string })?.message ?? String(err));
```

**Return both a text and a structured payload.** Agents differ in which they
read, and a human reading the transcript needs the text:

```ts
return {
  ok: {
    content: [{ type: 'text', text: humanReadableSummary }],
    structuredContent: { /* the machine-readable object */ },
  },
};
```

## A.6 App lifecycle

```rust
// src-tauri/src/lib.rs
tauri::Builder::default()
    .manage(mcp::McpState::default())
    .manage(mcp::bridge::McpBridge::default())
    .invoke_handler(tauri::generate_handler![
        mcp::mcp_get_status,
        mcp::mcp_set_enabled,
        mcp::mcp_regenerate_token,
        mcp::bridge::mcp_tool_result,
    ])
    .setup(|app| {
        tray::setup(app.handle())?;
        mcp::init(app.handle());   // starts the listener only if previously enabled
        Ok(())
    })
    .on_window_event(|window, event| {
        // Closing hides rather than quits: the MCP server lives in this
        // process, and an agent calling a tool needs the webview alive.
        if let WindowEvent::CloseRequested { api, .. } = event {
            if window.label() == "main" {
                api.prevent_close();
                let _ = window.hide();
            }
        }
    })
```

Three requirements that come with tray residency:

- **A tray icon with an explicit Quit.** If close only hides, the user must have
  a way out that is not Task Manager.
- **MCP off by default.** `mcp::init` starts the listener only when the user
  previously enabled it. Opening a local port is a decision, not a default.
- **Background throttling disabled** on the main window
  (`"backgroundThrottling": "disabled"` in `tauri.conf.json`). A hidden webview
  otherwise has its timers throttled, and any polling loop inside a tool call
  slows to a crawl exactly when nobody is watching. Verify this on **both**
  WebView2 and WKWebView — they throttle differently.

## A.7 The settings screen

Non-negotiable, because the address and token are per-install: **no documentation
you write can be correct**. The screen is the source of truth.

It must show:

| Element | Why |
|---|---|
| On/off switch | MCP is opt-in |
| The **bound** URL, e.g. `http://127.0.0.1:45817/mcp` | Not the preferred port — the bound one |
| Token, masked, with reveal + copy | Copy is how it gets into a config without a screenshot |
| Regenerate token button | The only remediation if it leaks |
| A "port changed" warning when `port_changed` is set | The otherwise-undiagnosable failure |
| `last_error` when the listener failed | Otherwise "enabled but not running" is silent |
| A plain-language trust note | See [G](#part-g--security-model) |

Render **two** copy-paste snippets from live status. Agents fall into two camps
and you cannot predict which one the user has:

```ts
const url = `http://127.0.0.1:${port}/mcp`;

// 1. For agents that configure themselves from a prompt
const agentPrompt =
  `Add an MCP server named "<<YOUR APP>>" at ${url} using Streamable HTTP transport, ` +
  `with the header "Authorization: Bearer ${status.token}". It runs locally on this ` +
  `machine. Once connected, list its tools and tell me what you can do.`;

// 2. For agents configured by file
const hermesYaml = `# ~/.hermes/config.yaml
mcp_servers:
  <<your_app>>:
    url: "${url}"
    headers:
      Authorization: "Bearer ${status.token}"`;
```

## A.8 If your app is not Tauri

The architecture is transport-shaped, not framework-shaped. What changes:

| Stack | Listener | Bridge |
|---|---|---|
| **Electron** | `http` server in the main process | `webContents.send` + `ipcMain.handle` reply, same UUID/oneshot pattern (a `Map<string, resolve>`) |
| **Pure web frontend + local sidecar** | Node/Go/Rust sidecar process | WebSocket between sidecar and page; the page must reconnect, which Tauri's event bus gives you free |
| **Native app, no webview** | Same axum listener | No bridge at all — handlers are just functions. You lose nothing except the reason the bridge existed |

The rest of this playbook — tool design, long-poll contract, run registry,
Telegram operations — applies unchanged.

### Verify Part A before going on

```bash
# 1. Unauthenticated request is refused
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:45817/mcp \
  -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","id":1,"method":"ping"}'
# → 401

# 2. Handshake
curl -s -X POST http://127.0.0.1:45817/mcp \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}'
# → result.protocolVersion, result.capabilities.tools

# 3. The bridge is alive (this one round-trips through the webview)
curl -s -X POST http://127.0.0.1:45817/mcp \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
# → result.tools[]
```

If (2) works and (3) times out after ~150 s, the listener is fine and the
**bridge** is not: the webview never started, or `startMcpBridge()` was never
called, or it was called inside a component that unmounted.

Then run the official inspector, which checks conformance you will not think of:

```bash
npx @modelcontextprotocol/inspector
# transport: Streamable HTTP · URL: http://127.0.0.1:<port>/mcp
# header:    Authorization: Bearer <token>
```

---

# Part B — Designing the tool surface

The server is the easy half. The tool surface is what decides whether an agent
is useful or dangerous.

## B.1 Granularity

Model tools on **user intentions**, not on your database tables or your REST
endpoints. The test: could a competent assistant, given only your tool list,
complete a real task without inventing anything?

Our shipped surface, as a shape to borrow:

| Category | Tools | Purpose |
|---|---|---|
| Discovery | `list_workflows`, `list_workflow_templates`, `list_projects`, `list_templates` | "What do I have?" |
| Inspection | `get_workflow` | "What does this need before it can run?" |
| Execution | `run_workflow`, `generate` | Do the thing |
| Polling | `get_run` | Long-running work |
| Reading results | `list_project_outputs`, `list_project_images` | "What did it produce?" |
| Portability | `export_template`, `export_workflow`, `import_json` | Move work in and out |

Two lessons from that table:

**A listing tool per user-visible surface, not per table.** Our Library shows
"Projects" as one tab backed by *two* tables, so one concept needed two tools —
and an agent that only knew one of them reported half the user's work as
missing.

**A "what did it produce" tool that covers every output type.** Ours began as
`list_project_images` only. An agent asked for the script a step had written,
found nothing (it was text), concluded the step had never run, and offered to
regenerate it — proposing to spend the user's money to recover something that
was sitting in the database. Cover every modality from day one.

## B.2 Descriptions are prompt, not documentation

The `description` is the only instruction the agent gets. Write it as guidance
to a colleague, and encode the workflow rules you actually want followed:

```ts
description:
  'Inspect one chain before running it: its steps in order, what each produces, ' +
  'which values the user must supply per step, and which arrive automatically ' +
  'from an earlier step. Call this after the user picks a workflow. Then ask them ' +
  'TWO things — run all steps at once or one step at a time, and the values listed ' +
  'in required_inputs — before calling run_workflow. Prompts, models and wiring are ' +
  'designed in the desktop app and cannot be changed from here. ' +
  'Results are read LIVE at call time and go stale the moment the user edits ' +
  'anything in the app - always call this again before answering questions about ' +
  'current config; never reuse an earlier result.'
```

That last sentence was added after an agent answered a config question from
memory — "Sudah dicek sebelumnya" — and reported values the user had changed
minutes before. If freshness matters, say so **in the tool description**;
nowhere else reaches the agent.

## B.3 What a tool must never return

Draw this line explicitly and write it at the top of the module:

- **Never:** API keys, vault contents, tokens, another user's rows.
- **Inspection tools return shape, not recipe.** `get_workflow` reports that a
  step takes `product_name` and outputs an image — it does not return the
  authored prompt.
- **Export tools may return everything the user authored**, because a
  prompt-less export cannot be re-imported and the format exists to move the
  user's own work. Gate them on ownership, and name them so the intent is
  obvious (`export_*`).

## B.4 The long-poll contract

No SSE means no progress notifications. Hybrid long-poll replaces them:

```
run_workflow(wait_seconds = 100, max 120)
   ├── finished in time  → full result, status "success" | "error"
   └── still running     → { status: "running", run_id }  → agent calls get_run
```

Rules:

- `wait_seconds` default well under the bridge timeout (100 vs 150), hard-capped
  (120). Never let a caller request a wait longer than the bridge will allow —
  the agent gets a timeout error instead of the run id it needed to recover.
- The reply shape for "still running" is **the same shape** as the finished
  reply, plus `status`. An agent should not need two parsers.
- `get_run` takes the same `wait_seconds`, so polling is cheap for the agent:
  it can block for another 100 s rather than spinning.

## B.5 The run registry

A run must outlive the tool call that started it, and must not live inside your
UI framework's component tree.

```ts
// src/lib/mcp/runRegistry.ts — module-level, framework-free
const runs = new Map<string, RunRecord>();
const cancelled = new Set<string>();

export const MAX_CONCURRENT_RUNS = 1;
export const MAX_RUNS_PER_HOUR = 10;

export function startRun(...): RunRecord {
  const record: RunRecord = { run_id: newRunId(), status: 'running', /* … */ };
  runs.set(record.run_id, record);
  prune();                                   // cap retained finished runs

  // Not awaited: the whole point is that the run outlives the tool call.
  // driveWorkflow never throws, so an unhandled rejection is not possible.
  void driveWorkflow(record, inputs, () => cancelled.has(record.run_id));
  return record;
}

export async function awaitRun(runId: string, waitSeconds: number) {
  const deadline = Date.now() + waitSeconds * 1000;
  for (;;) {
    const record = runs.get(runId);
    if (!record || record.status !== 'running') return record;
    if (Date.now() >= deadline) return record;
    await new Promise((r) => setTimeout(r, 250));
  }
}
```

Deliberately **memory-only**: the durable state is already in your database, so
a restart loses only the agent's "which run was that" mapping. If you need
resume across restarts, persist a provider task id (we keep
`prompt_generations.provider_task_id`) rather than trying to persist the
registry itself.

### The headless driver

Your UI almost certainly drives multi-step work from a hook or a component. MCP
needs the same loop with no React in it. Expect this to be the largest single
piece of new code — it was for us. Extract the step executor first, then write
the loop around it; do not try to reuse the hook.

## B.6 Guardrails

With user-supplied provider keys there is no spend ceiling to enforce, so
**run-count caps are the honest guardrail** against a looping agent:

```ts
if (countActiveRuns() >= MAX_CONCURRENT_RUNS)
  return fail(TOOL_FAILED, 'A run is already in progress. Retry when it finishes.');

if (countRunsSince(Date.now() - 3600_000) >= MAX_RUNS_PER_HOUR)
  return fail(TOOL_FAILED, `Rate limit reached (${MAX_RUNS_PER_HOUR} runs per hour).`);
```

Also worth having: a per-object `mcp_enabled` flag so a user can withhold
specific work from agents, and an audit column tagging rows with
`trigger_source='mcp'` so an MCP-driven action is distinguishable afterwards.

## B.7 Missing input is a result, not an error

The single highest-value pattern in the whole surface:

```ts
// Return the precise list rather than failing generically.
const missing = findMissingInputs(steps, inputsByStep, scope);
if (missing.length > 0) {
  return {
    ok: {
      content: [{ type: 'text', text: 'Butuh input berikut sebelum bisa dijalankan…' }],
      structuredContent: { status: 'needs_input', missing },
    },
  };
}
```

An agent told *"what should I put in `product_name` for step 1"* asks the user.
An agent told *"invalid arguments"* invents a value. Also: perform this check
**before** any side effect — ours creates a project from a template only after
the input check passes, so `needs_input` leaves nothing behind.

## B.8 Per-tool checklist

Before shipping a tool, answer all eight:

1. Does it map to something a user would ask for in words?
2. Does the description tell the agent *when* to call it and what to do next?
3. `additionalProperties: false`, and every field described?
4. Can it leak a secret, another user's data, or authored content that
   inspection should not return?
5. Does every failure produce a message a human could act on?
6. If it can run long: does it long-poll, cap the wait, and return a poll handle?
7. Does it cost money or make an irreversible change? If so — is it capped,
   and does the description tell the agent to confirm with the user first?
8. Is it tested through `dispatchMcp`, not just as an inner function? (See
   [Part E](#part-e--testing).)

---

# Part C — Hermes and Telegram

## C.1 Topology

The whole design assumes **agent and app on the same machine**: localhost MCP,
no tunnel, results handed over as absolute file paths.

```
Telegram servers
      ▲  │  long polling (outbound HTTPS only — no public URL, no port forward)
      │  ▼
   Hermes Agent ──── MCP ────► 127.0.0.1:<port>  YOUR APP
   (same box)
```

Telegram's `getUpdates` long polling is what makes this work from a home
machine: the bot dials out, so **no inbound connectivity, no static IP and no
HTTPS certificate are required**. `setWebhook` is the opposite trade — it needs
a public HTTPS URL, and setting it *disables* `getUpdates`. Use polling unless
you already have public infrastructure.

If the agent must run elsewhere (a VPS), you have three options, in order of
preference:

1. **Move the agent to the machine.** Almost always right.
2. **A private tunnel** (Tailscale/WireGuard) so `127.0.0.1` becomes a private
   address the agent can reach. Keep the bearer token; add nothing to the
   public internet.
3. **Expose the port publicly.** Do not. The token was designed for a
   same-OS-user trust model, not for the open internet, and file-path handover
   stops working the moment the agent is not on the same disk.

## C.2 Configuring Hermes

From Settings → MCP, copy the generated block: 〔verify the exact key names
against your Hermes version〕

```yaml
# ~/.hermes/config.yaml
mcp_servers:
  <<your_app>>:
    url: "http://127.0.0.1:45817/mcp"
    headers:
      Authorization: "Bearer <per-install token>"
```

Tools then appear to the agent as `mcp_<<your_app>>_<tool>` 〔naming convention
is Hermes-specific — confirm from its tool listing〕.

Checklist for the connection:

- [ ] App running and visible in the tray
- [ ] MCP toggle **on** in Settings
- [ ] URL uses the **bound** port from the settings screen, not a remembered one
- [ ] Token copied whole (32 bytes → 64 hex chars)
- [ ] The app is signed in — tools that need a session fail clearly if not
- [ ] Hermes restarted after editing its config

## C.3 Conversation design

This is where most of the perceived quality lives. Put the rules in the tool
descriptions (the agent reads those), and mirror them in the Hermes system
prompt (the agent reads that too):

```
When the user asks to run something in <<YOUR APP>>:
1. list_workflows / list_workflow_templates → show names and ask which one.
2. get_workflow → read required_inputs. NEVER invent values. Ask the user for
   each one, in Indonesian, one message, as a numbered list.
3. Ask: run everything at once, or step by step?
4. run_workflow. If status is "running", tell the user it started and poll
   get_run — do not go silent.
5. Report each step's output as it lands. Send media as files, not links.
6. Before re-running a step, call list_project_outputs — a result that already
   exists costs nothing to read and the user already paid for it.
Never call get_workflow once and answer later questions from memory: config
changes in the app and your copy goes stale immediately.
```

Rule 6 exists because an agent proposed regenerating a script that was already
in the database. Rule 4 exists because a silent agent during a two-minute video
render is indistinguishable from a crash.

## C.4 Getting results back to the user

Your app writes outputs somewhere (object storage, database, disk). Telegram
needs bytes or a URL. Decide once:

| Output | Recommended |
|---|---|
| Text | Send inline. Telegram caps a message around 4096 characters — chunk on paragraph boundaries, never mid-word |
| Image | `sendPhoto` with the local file |
| Video | `sendVideo` with the local file; send a short "rendering…" message first |
| Large file | The standard Bot API server caps per-file uploads well below typical video sizes; a **local Bot API server** raises it to 2000 MB. Otherwise send a link |

This is why MCP tools hand back **absolute local paths**: `sendPhoto` with a
path is one call, whereas a signed URL means the agent must download, hold
bytes in memory, and re-upload. If your outputs live in cloud storage, download
them to a predictable directory as part of finishing a run:

```
~/<<YourApp>>/Library/runs/<run_id>/step-1.png
```

## C.5 Multi-user and identity

The MCP token authenticates a *machine-local process*, not a person. If several
people can message the bot, **Hermes must do the authorization**: keep an
allow-list of Telegram user ids and refuse everyone else. The desktop app has
exactly one signed-in account and cannot tell two Telegram users apart —
do not push that decision down to it.

---

# Part D — Bring-up, end to end

Each step has a verification. Do not proceed past a red one.

| # | Step | Verify |
|---|---|---|
| 1 | Add deps, create the five files, register state + commands | `cargo check` clean |
| 2 | `check_bearer` + its unit tests | `cargo test` green |
| 3 | Listener with port fallback; enable from settings | Settings shows *running* + a bound port |
| 4 | `initialize` / `ping` in Rust | curl (2) above returns a result |
| 5 | Bridge both halves; `startMcpBridge()` at boot | curl (3) returns `tools[]` |
| 6 | One trivial read-only tool (`list_*`) | Its rows come back through curl |
| 7 | MCP Inspector against the endpoint | Handshake + tool list + one call, no warnings |
| 8 | Tray residency; close → hide | Tool call still answers with the window closed |
| 9 | Long-running tool + run registry + `get_run` | A run started, returned `running`, polled to completion |
| 10 | Guardrails | Second concurrent run refused with a readable message |
| 11 | Hermes config from the settings screen | Hermes lists your tools by name |
| 12 | Telegram end to end | "list my workflows" → real names on the phone |
| 13 | Hidden-window run | Full run completes with the window hidden, on every OS you ship |
| 14 | Restart mid-run | Behaviour is understood and documented (ours does not resume) |

Step 13 is the one most likely to fail late and is easy to forget: WebView2 and
WKWebView throttle background timers differently, and a hidden window is the
*normal* state for this feature.

---

# Part E — Testing

What we actually test, and what it caught:

**Pure logic, unit-tested.** Anything that maps rows to agent-visible shapes:
schema derivation, output collection, model resolution. Cheap and fast.

**Handlers, tested through `dispatchMcp`.** This matters more than it sounds.
We once shipped a bug where the mapper was correct and fully unit-tested, but
the *loader* called it without the argument that carried the override — every
mapper test passed while the feature did nothing. Test the path the agent
takes:

```ts
const call = (name: string, args = {}) => dispatchMcp('tools/call', { name, arguments: args });

it('surfaces the saved override instead of the template default', async () => {
  const reply: any = await call('get_workflow', { workflow_id: 'wp-1' });
  expect(reply.ok.structuredContent.steps[0].model_key).toBe('veo3_lite');
});
```

**Guardrails, explicitly.** Concurrency refusal, hourly cap, `needs_input`
before side effects, unknown tool name, missing required argument.

**Auth, in Rust.** The four malformed-header cases above.

**Traps we hit, so you can skip them:**

- A test that passes for the wrong reason. One of ours asserted an error
  message that appeared on *both* the intended path and the fallback path — it
  was green while never reaching the code under test. Assert something only the
  intended path can produce (`expect(submitVideoTask).toHaveBeenCalled()`).
- Scripted patches that fail silently. If you edit files with a script, **grep
  for the result afterwards**. We twice believed a fix was applied when the
  script had thrown before writing, and TypeScript stayed green because nothing
  referenced the missing function.
- Mocking the database client instead of the query builder. Chained builders
  (`.from().select().eq().maybeSingle()`) need a chainable fake; a plain
  `vi.fn()` breaks at the second link.

---

# Part F — Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Agent: "connection refused" | App not running, MCP off, or **the port moved** | Settings → MCP; re-copy the URL. This is why `port_changed` exists |
| `401` on every call | Token truncated on copy, or regenerated since the config was written | Re-copy from settings; restart the agent |
| Handshake works, `tools/list` hangs ~150 s | Bridge is dead: webview closed, `startMcpBridge()` never ran, or it ran inside an unmounted component | Move the call to app boot |
| Tool returns `[object Object]` | A non-`Error` thrown value stringified | Use the `errMessage` helper |
| Agent reports stale config | It cached an earlier `get_workflow` | Add the freshness sentence to the description |
| Long run returns a timeout instead of a run id | `wait_seconds` ≥ bridge timeout | Cap it below; derive from `BRIDGE_TIMEOUT` |
| Runs crawl when the window is hidden | Background throttling | `backgroundThrottling: "disabled"`; re-verify per platform |
| Agent invents input values | `required_inputs` not surfaced, or no `needs_input` result | Implement B.7 |
| Second run silently queues forever | No concurrency guard | Implement B.6 |
| Everything works, agent still won't use a tool | Description does not say when to call it | Rewrite it as instruction |

---

# Part G — Security model

State this plainly in the settings UI, not only in a document:

- The listener binds **`127.0.0.1` only**. Nothing outside the machine can
  reach it.
- The bearer token is 32 random bytes, per install, at
  `<app_config_dir>/mcp-token`, `0600` on Unix, compared in constant time,
  regenerable from settings.
- **Same-OS-user trust:** any process running as this user can read the token
  file and therefore use the tools — which, with BYOK, means using the user's
  provider credit. That is the accepted boundary; say so where the user will
  see it, not in a footnote.
- MCP is **off until switched on**.
- Tool calls require a live authenticated session. If it dies, tools fail with
  a clear "not signed in" message rather than hanging.
- Secrets never cross the MCP boundary in either direction.

What this model does **not** cover, and you should not pretend otherwise:
malware already running as the user; a shared/multi-user desktop; and any
scenario where the port is exposed beyond loopback.

---

# Part H — Port checklist

```
Rust
[ ] deps: tokio, axum, uuid, rand, subtle
[ ] mcp/auth.rs      token gen/persist/0600, constant-time bearer, config file
[ ] mcp/auth.rs      unit tests for check_bearer
[ ] mcp/mod.rs       McpState, McpStatus, init(), 3 commands
[ ] mcp/server.rs    bind_with_fallback + persist bound port + port_changed
[ ] mcp/server.rs    initialize / ping / notifications-202 / 405 on GET
[ ] mcp/bridge.rs    oneshot map, emit, timeout, cleanup on every exit path
[ ] lib.rs           manage state, register commands, tray, close→hide
[ ] tauri.conf.json  backgroundThrottling: disabled

TypeScript
[ ] lib/mcp/bridge.ts   listen, dispatch, always reply once
[ ] main.tsx            startMcpBridge() at boot
[ ] lib/mcp/tools.ts    TOOL_DEFINITIONS, HANDLERS, dispatchMcp, errMessage
[ ] lib/mcp/runRegistry.ts  startRun/awaitRun/getRun, caps, prune
[ ] headless driver     the loop your UI hook currently owns
[ ] settings screen     live URL + token + regenerate + port-changed warning
[ ] settings screen     agent-prompt snippet AND config-file snippet

Tools
[ ] discovery / inspection / execution / polling / results / portability
[ ] needs_input before any side effect
[ ] concurrency + rate caps
[ ] freshness sentence in every inspection tool description
[ ] tests through dispatchMcp, not just inner functions

Ops
[ ] Hermes config from the settings screen
[ ] Telegram bot via getUpdates polling
[ ] Telegram allow-list in the agent
[ ] outputs downloaded to predictable local paths
[ ] verified with the window hidden, on every OS you ship
```

---

## Appendix — reference files in this repo

| Concern | File |
|---|---|
| State, commands, status | `src-tauri/src/mcp/mod.rs` |
| Token, config, bearer check | `src-tauri/src/mcp/auth.rs` |
| Listener, port fallback, JSON-RPC | `src-tauri/src/mcp/server.rs` |
| Rust→webview bridge | `src-tauri/src/mcp/bridge.rs` |
| Webview→Rust reply | `src/lib/mcp/bridge.ts` |
| Tool schemas + handlers | `src/lib/mcp/tools.ts` |
| Run registry | `src/lib/mcp/runRegistry.ts` |
| Headless driver | `src/lib/mcp/runner.ts` |
| Agent-facing shape derivation | `src/lib/mcp/workflowSchema.ts` |
| Output collection (all modalities) | `src/lib/mcp/projectOutputs.ts` |
| Settings screen | `src/components/settings/McpSettings.tsx` |
| Tray residency | `src-tauri/src/tray.rs` |
| Design decision record | `docs/hermes-mcp-integration.md` |

## Appendix — protocol notes

- Transport implemented here is **stateless Streamable HTTP**: a single
  `POST /mcp`, one JSON response per JSON-RPC request. No SSE, no session ids.
- `SUPPORTED_PROTOCOL_VERSIONS` in `server.rs` currently lists `2025-06-18`,
  `2025-03-26`, `2024-11-05`. The specification has published later revisions
  (`2025-11-25` at the time of writing) — add versions as you verify clients
  against them, and keep echoing the client's requested version when supported.
- The spec expects clients to send `Accept: application/json, text/event-stream`
  and permits a server without SSE to answer `GET /mcp` with **405**. Routing
  only `POST` gives you that for free.
- If a client ever *requires* SSE, replacing the internals of `server.rs` with
  the `rmcp` crate is a contained change — the bridge and every tool handler are
  unaffected.
- Authorization: the token goes in the `Authorization` header on every request,
  never in a query string.

## Appendix — external references

- MCP specification — transports, lifecycle, authorization:
  `https://modelcontextprotocol.io/specification/`
- MCP Inspector: `npx @modelcontextprotocol/inspector`
- Telegram Bot API — `getUpdates`, `setWebhook`, `sendPhoto`/`sendVideo`,
  local Bot API server: `https://core.telegram.org/bots/api`
