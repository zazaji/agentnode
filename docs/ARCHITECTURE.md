# AgentNode 3.2 Architecture

## Principles

1. Windows, Linux and macOS are first-class platform adapters.
2. Native API is preferred over GUI simulation when available.
3. Deterministic operations use direct APIs/shell; goal-oriented work uses Agent Runtime.
4. Privileged system context and interactive desktop context are separate processes on Windows.
5. Long-running activity is observable, cancellable and attributable.
6. Capabilities degrade independently; missing OCR/COM/CDP must not stop the core node.
7. File, shell, browser, Office and desktop scopes are independent security boundaries.

## Layers

### Interface
FastAPI REST, Web Console, local stdio MCP and remote Streamable HTTP MCP.

### Core
Authentication/RBAC, shell policy, jobs, events, audit, tool history, terminal sessions, files/search, process/service managers, config and code execution.

### Rich document plugin
`plugins/documents` provides XLSX/DOCX/PDF operations and reuses FileManager path authorization.

### Browser adapter
`browser/cdp.py` uses DevTools discovery plus WebSocket JSON-RPC. It is intentionally disabled by default.

### Office adapter
`office/com.py` provides Windows COM primitives for Excel/Word/PowerPoint. `office/manager.py` routes them to the interactive-user Desktop Worker by default so a LocalSystem Core does not attempt Office automation from Session 0. The public interface remains isolated from COM implementation details so future LibreOffice/native adapters can be added.

### Desktop Worker / Computer Use
Windows UI operations belong in the interactive-user Desktop Worker. UIA, Win32, screenshot, OCR, input and clipboard are exposed through DesktopManager.

### Unified Desktop Graph
`desktop/graph.py` creates one semantic observation graph from HWND windows, UIA nodes and OCR regions. Future vision grounding can add nodes/edges without changing the consumer-facing graph format.

### Agent Runtime and LLM registry
Pi RPC and custom runtimes are separate from provider/model configuration. Nodes can route planning, computer use, summarization, etc. to different profiles.

### Mesh
Peers are named AgentNodes. Delegation carries `trace_id` and `hops` to prevent recursive loops and permit end-to-end audit.

Three in-product coordination primitives:

- `POST /api/v1/mesh/delegate` — 1:1: send one task to one peer, return the peer's response with the shared `trace_id`.
- `POST /api/v1/mesh/coordinate` — 1:N fan-out: a coordinator sends the same task to many peers in parallel (or sequentially), aggregates `{peer: {ok, trace_id, response|error}}`, and reports unknown/unreachable targets separately. Partial failures do not fail the whole fan-out. The coordinator excludes itself; a peer running the same role (`mesh.delegate`) can itself fan out, so coordination is arbitrary-depth with `hops` still guarding against loops.
- `POST /api/v1/mesh/forward` — task relay (转交): hand one task off to an auxiliary (helper) node. The helper gate is `mesh.helper_key` (shared key, constant-time compared, sent in `X-AgentNode-Helper-Key`); a node without the key refuses to be a helper. Behaviour follows `mesh.forward_policy` (`off` keeps work local, `offload` hands off when in-flight load exceeds `offload_after`, `distribute` always picks the least-loaded helper) within a per-task relay budget (`forwards_left`, default from `max_forwards`). A task can be marked `forwardable: false` (not re-transferable): a node that received it via relay always executes locally, while an origin may still hand it off once with an explicit `target`. Loop avoidance is structural: every hop appends itself to `hops`, and both `_pick_target` and `coordinate`'s fan-out exclude every path member — a task (or any sub-task it coordinates) can never be handed back to an upstream node, and an explicit target already on the path is refused. Each hop's explicit `target` is consumed once; the downstream `ForwardRequest` carries `target: null` so the next node applies fresh policy. Path-member exclusion compares against each peer's declared `peers.<name>.node_id` (falling back to the config key), so upstream detection is by node identity, not by whatever local name the peer happens to be given.

RBAC: all three endpoints require `mesh.delegate` — held by the `node` role (plus `administrator`/`super`), but not by the `operator` role, so a plain operator can steer servers but cannot push delegated work through the mesh without the node identity. `forward` additionally requires the helper key.

## Preferred execution ladder

```text
Application/native API
  → COM/CDP/platform API
  → UI Automation/accessibility
  → Win32/OS controls
  → OCR/vision grounding
  → pixel input fallback
```

## Capability reporting

An unavailable optional backend returns capability/status information rather than preventing AgentNode from starting. This is required for mixed Windows/Linux/macOS fleets.
