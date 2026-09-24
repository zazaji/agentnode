# API Surface — 3.3

All production REST routes except `/` and `/health` use Bearer authentication.

## Node/jobs/runtime
- `GET /api/v1/node`
- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{id}`
- `GET /api/v1/jobs/{id}/events`
- `POST /api/v1/jobs/{id}/cancel`
- `GET /api/v1/runtime`
- `GET /api/v1/peers`
- `POST /api/v1/mesh/delegate`
- `POST /api/v1/mesh/coordinate`
- `POST /api/v1/mesh/forward`

### Mesh coordinate
1:N fan-out: `POST /api/v1/mesh/coordinate` with
`{"task": {"action": "shell"|"agent", "payload": {...}}, "peers": ["name", ...] | null, "parallel": bool, "timeout_s": number}`.
The coordinator excludes itself, resolves unknown peers into `unknown`, delegates to the rest in parallel (or sequentially when `parallel:false`), and returns
`{trace_id, coordinator, parallel, targets, unknown, results: {peer: {ok, trace_id, response|error}}}`.
Partial failures do not fail the whole fan-out. Requires `mesh.delegate` scope (node/administrator/super). CLI: `agentnode mesh-coordinate --peer <name> [--peer ...] --command 'cmd'` (reads `AGENTNODE_ADMIN_TOKEN`; `--tool agent --prompt` for agent tasks, `--sequential` for serial fan-out).

### Mesh forward (task relay / 转交)
Hands one task off to a helper node (auxiliary-node gating):
`POST /api/v1/mesh/forward` with
`{"task": {"action": "shell"|"agent", "payload": {...}}, "target": "name"|null, "forwardable": bool, "policy": {"mode":"off"|"offload"|"distribute","max_forwards":int}|null, "forwards_left": int|null, "trace_id": str|null, "hops": [str]}`.
Requires `mesh.delegate` scope AND the `X-AgentNode-Helper-Key` header matching the local `mesh.helper_key`; a node without a helper key (or a wrong key) returns 403.
- `target` is a per-hop explicit hand-off (consumed by that hop; refused if it is already on the request path — cannot send a task back upstream).
- `forwardable:false` marks the task not re-transferable: any node that received it via relay executes it locally; an origin may still hand it off once with an explicit `target`.
- Default behavior follows `mesh.forward_policy` (`off`/`offload` with `offload_after`/`distribute` with least-loaded selection, `max_forwards` relay budget).
- Returns `{trace_id, node_id, action, forwarded_to, hops, response}` where a local run embeds the shell/agent result.
CLI: `agentnode mesh-forward --target <node> [--command 'cmd'|--prompt '...'] [--mode off|offload|distribute] [--max-forwards N] [--no-forwardable]` (reads `AGENTNODE_ADMIN_TOKEN` and `AGENTNODE_HELPER_KEY` env vars).

## Shell/code/terminal
- `POST /api/v1/shell`
- `POST /api/v1/code`
- `POST /api/v1/terminal`
- `GET /api/v1/terminal`
- `GET /api/v1/terminal/{id}`
- `POST /api/v1/terminal/{id}/write`
- `DELETE /api/v1/terminal/{id}`

## Files/search
- `POST /api/v1/files/read`
- `POST /api/v1/files/read-smart`
- `POST /api/v1/files/read-multiple`
- `POST /api/v1/files/write`
- `POST /api/v1/files/replace`
- `GET /api/v1/files/info`
- `GET /api/v1/files/list`
- `POST /api/v1/files/mkdir`
- `POST /api/v1/files/move`
- `POST/GET/DELETE /api/v1/searches...`

## Documents
- `GET /api/v1/documents/capabilities`
- `POST /api/v1/documents/xlsx/read`
- `POST /api/v1/documents/xlsx/set-range`
- `POST /api/v1/documents/xlsx/append`
- `POST /api/v1/documents/docx/read`
- `POST /api/v1/documents/docx/create`
- `POST /api/v1/documents/docx/replace`
- `POST /api/v1/documents/pdf/read`
- `POST /api/v1/documents/pdf/merge`

## Desktop/computer use
- `GET /api/v1/desktop/observe`
- `GET /api/v1/desktop/tree`
- `GET /api/v1/desktop/windows`
- `POST /api/v1/desktop/window`
- `POST /api/v1/desktop/uia/find`
- `POST /api/v1/desktop/uia/invoke`
- `POST /api/v1/desktop/act`
- `GET /api/v1/desktop/graph`
- `GET/POST /api/v1/clipboard`

## Browser/CDP
- `GET /api/v1/browser/status`
- `GET /api/v1/browser/tabs`
- `POST /api/v1/browser/navigate`
- `POST /api/v1/browser/evaluate`
- `GET /api/v1/browser/{target_id}/snapshot`
- `GET /api/v1/browser/{target_id}/screenshot`
- `POST /api/v1/browser/click`
- `POST /api/v1/browser/type`
- `POST /api/v1/browser/tabs/new`
- `DELETE /api/v1/browser/tabs/{target_id}`

## Windows Office COM
- `GET /api/v1/office/status`
- `POST /api/v1/office/excel/read`
- `POST /api/v1/office/excel/write`
- `POST /api/v1/office/excel/format`
- `POST /api/v1/office/word/read`
- `POST /api/v1/office/word/replace`
- `POST /api/v1/office/word/insert-table`
- `POST /api/v1/office/powerpoint/read`
- `POST /api/v1/office/powerpoint/add-text-slide`

## Audit/config
- `GET /api/v1/audit`
- `GET /api/v1/history`
- `GET /api/v1/usage`
- `GET/POST /api/v1/config`

Remote Streamable HTTP MCP is mounted at `/mcp`; local stdio MCP is available with `agentnode mcp-stdio`.
