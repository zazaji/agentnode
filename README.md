# AgentNode 3.2

**Give AI agents a real computer, not just a shell.**

AgentNode is a cross-platform MCP/REST computer-use runtime for Windows, Linux and macOS. Version 3.2 builds on the Desktop Commander parity work in 3.1 and adds five product-grade capability families: rich document plugins, native browser automation through Chrome DevTools Protocol, Windows Office COM automation, a Unified Desktop Graph, and official MCP conformance CI wiring.

## Architecture

```text
Remote Agent / Browser / Local MCP Client
              │
     MCP HTTP / stdio / REST / Web
              │
┌─────────────▼────────────────────────────┐
│ AgentNode Core                           │
│ RBAC · jobs · audit · search · history  │
│ mesh · LLM registry · runtime routing   │
└──────┬───────────────┬───────────┬──────┘
       │               │           │
Desktop Cmdr      Document     Browser/Office
Shell/File/       Plugins      CDP / COM
Terminal/Search   XLSX/DOCX/PDF   │
       │               │           │
       └──────────┬────┴─────┬─────┘
                  │          │
          Privileged Core  Desktop Worker
          SYSTEM/root      logged-in session
                  │          │
                  └────┬─────┘
                       ▼
                Unified Desktop Graph
                HWND + UIA + OCR
                       │
                       ▼
                Local Agent Runtime
                Pi / custom runtime
```

On Windows the privileged service and interactive Desktop Worker stay separate because Session 0 must not be treated as the logged-in desktop.

## Mesh coordination (3.2.1)

AgentNode's 1:1 mesh delegation is extended with autonomous fleet coordination:

- `POST /api/v1/mesh/coordinate` fans one task out to many peers (parallel or
  sequential) and aggregates `{peer: {ok, trace_id, response|error}}`; unknown
  peers are separated into `unknown`, and partial failures never fail the batch.
- Coordination is recursive — any node with `mesh.delegate` can act as a
  coordinator of coordinators — while `trace_id`/`hops` still guard against loops.
- `agentnode mesh-coordinate --peer <name> ... --command 'cmd'` triggers a
  coordinate directly from the CLI on the local node.

Verified live: a 4-node fleet (debian + zjdebian10 + ser117 + win10), connected
across NAT with direct LAN legs plus reverse-SSH tunnel legs, where one call from
any node dispatches `hostname` to the rest and returns all results.

## Task relay / auxiliary nodes (3.3.0)

Nodes can act as **auxiliary (helper) nodes** gated by a configured shared key,
and tasks can be **handed off (转交)** between nodes under a configurable policy:

- `mesh.helper_key` — a node only serves `/api/v1/mesh/forward` when it holds the
  shared key (sent in the `X-AgentNode-Helper-Key` header, constant-time
  compared). No key configured → the node refuses to be a helper.
- `mesh.forward_policy` — `mode: off|offload|distribute`:
  - `offload` hands the task off to a helper when in-flight load exceeds
    `offload_after`;
  - `distribute` always picks the least-loaded available helper;
  - `max_forwards` caps the relay budget (how many hops a task may take).
- Per-task `forwardable: false` marks a task as **not re-transferable**: a node
  that received it via relay always executes it locally; an origin that sets it
  may still hand it off once with an explicit `target`.
- **Loop avoidance:** every hop appends itself to `hops`; a forward target is
  never chosen from path members, so a task can never be handed back to its
  upstream node, and sub-tasks coordinated by a relayed node can never fan back
  upstream either. An explicit target already on the path is refused. Each peer
  should declare `node_id` in its mesh entry so loop-avoidance compares node
  identity, not the local peer config key.

`agentnode mesh-forward --target <node> --command 'cmd'` triggers a hand-off from
the CLI; `--no-forwardable` marks the task as not re-transferable and `--mode`
overrides the relay policy for that task.

## New in 3.2

### Rich document plugin

Optional plugin with explicit `document.read` / `document.write` scopes:

- XLSX: read workbook/sheet/range, set rectangular values, create workbook, append rows.
- DOCX: read paragraphs/tables, create documents, scoped text replacement.
- PDF: page text extraction and PDF merge.
- All document paths reuse the same FileManager allowed-root guard.
- Writes use temporary files + atomic replace where supported.

Install:

```bash
pip install -e '.[documents]'
```

### Browser/CDP

Browser automation is a separate capability from desktop pixel input. When enabled, AgentNode talks to a local Chrome/Edge DevTools endpoint and can:

- enumerate browser targets/tabs;
- inspect DevTools version/status;
- navigate/create/close browser targets;
- capture structured DOM/text snapshots and screenshots;
- click/type through CSS selectors;
- execute JavaScript through `Runtime.evaluate`;
- cap snapshot/screenshot payloads to protect the node.

This is preferred over mouse automation when a browser exposes CDP.

```yaml
browser:
  enabled: true
  cdp_url: http://127.0.0.1:9222
```

Start Chrome/Edge with a dedicated remote-debugging profile; do not expose the debugging port to untrusted networks.

### Windows Office COM

Optional Windows-only adapter using `win32com`:

- Excel range read/write and formatting;
- Word document text read/replace and table insertion;
- PowerPoint read and text-slide creation;
- explicit `office.read` / `office.write` scopes;
- disabled by default.

```yaml
office:
  enabled: true
```

On Windows, Office calls are routed to the interactive-user Desktop Worker by default. Silent fallback to the Session-0 Core is disabled unless `office.allow_core_fallback=true` is explicitly configured.

### Unified Desktop Graph

`GET /api/v1/desktop/graph` fuses:

- Win32 top-level windows / HWNDs;
- UI Automation tree nodes;
- OCR regions when requested;
- stable node IDs, containment edges and a graph hash.

The graph is the semantic observation surface for future vision grounding and verified computer-use planning. OCR Provider representation is normalized so RapidOCR, Windows OCR and future OmniParser adapters do not change the public contract.

### Richer Web Console

The console now contains dedicated views for:

- Jobs / events / stdout / stderr;
- Terminal sessions;
- Search sessions;
- smart file preview with inline image rendering;
- document capability/XLSX preview;
- Unified Desktop Graph;
- CDP browser targets/navigation;
- history/usage/config/runtime/peers.

### MCP protocol surface

`/mcp` (streamable HTTP) and MCP stdio share the same RBAC scopes as the REST API: unauthenticated posts are rejected (`401`) and unauthorized tool calls answer `isError` with `403 scope required: ...`. Protocol behavior is validated against the official `@modelcontextprotocol/conformance` scenario runner in the private project workspace (see `docs/MCP_CONFORMANCE.md`).

The production `/mcp` endpoint continues to require Bearer authentication.

AgentNode's current production authentication is static scoped Bearer tokens. Full OAuth 2.1 resource-server conformance is therefore intentionally tracked as a separate security milestone rather than being falsely claimed by the static-token mode.

## Existing 3.1/3.0 capabilities

- Native PowerShell/CMD on Windows, Bash on Linux, Zsh on macOS.
- Foreground/background Jobs, timeouts, progress/events and process-tree cancellation.
- Long Terminal Sessions with stdout/stderr source, cursor paging and owner isolation.
- Smart files: paged text, DOCX/XLSX/PDF reading, image metadata/preview, binary detection.
- Progressive Search Sessions with ripgrep acceleration, pagination and cancellation.
- Atomic rewrite/append/move/mkdir/info/list and guarded fuzzy replacement.
- Persistent tool history, usage statistics and secret redaction.
- Python/Node/R code executor.
- Process and SCM/systemd/launchd service management.
- Screenshot, Windows UIA, Win32 window control, input, OCR and clipboard.
- Pi RPC Agent Runtime + configurable runtimes and LLM routing.
- Agent Mesh with trace IDs, hop limits, loop prevention, and 1:N coordinate fan-out.
- local stdio MCP + remote Streamable HTTP MCP + REST + Web Console.

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -e '.[mcp,documents]'
agentnode init --config config.yaml
agentnode serve --config config.yaml
```

`agentnode init` prints raw tokens once; configuration stores hashes only.

Open `http://127.0.0.1:8765/` and provide a token.

## Security model

AgentNode does **not** claim that allowed file roots sandbox a shell. Important boundaries are separate:

1. File path guard.
2. Shell policy and explicit super mode.
3. RBAC capability scopes.
4. Desktop input scopes.
5. Browser/Office/document scopes.
6. Windows privileged-core vs interactive Desktop Worker separation.
7. Mesh hop/trace loop protection.

High-impact features are disabled by default when they expose an additional control plane (`browser.enabled`, `office.enabled`, `shell.allow_super_mode`). HTTP request bodies are bounded and Trusted Host validation is enabled. Remote deployments must add their DNS name/IP to `http.trusted_hosts`.

## Building and validation

```bash
pip install -e '.[documents]'
python -m compileall -q src
python -m build --wheel
```

Unit/integration tests are run privately in the project workspace and are not
published with the public repository. See `docs/ARCHITECTURE.md`, `docs/API.md`,
and `docs/MCP_CONFORMANCE.md`.

## Attribution

Desktop Commander MCP is MIT licensed. AgentNode contains Python ports/reimplementations of selected behavior learned from Desktop Commander v0.2.51; required attribution remains in `THIRD_PARTY_NOTICES.md`.

## Version

**3.3.0**
