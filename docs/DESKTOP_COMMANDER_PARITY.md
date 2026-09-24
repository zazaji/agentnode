# Desktop Commander parity review

Compared against Desktop Commander MCP v0.2.51 source.

| Capability | Desktop Commander | AgentNode 3.0 | AgentNode 3.1 |
|---|---:|---:|---:|
| Long-running terminal session | Yes | Basic | Enhanced cursor/source/eviction/wait-state |
| Interactive process input | Yes | Yes | Yes |
| Session listing | Yes | No | Yes |
| Bounded terminal output | Yes | Basic deque | Yes + eviction metadata |
| Progressive search session | Yes | No | Yes |
| Search paging / cancel / list | Yes | No | Yes |
| ripgrep acceleration | Yes | One-shot | Yes + fallback |
| DOCX content search | Yes | No | Yes |
| XLSX content search | Yes | No | Yes |
| Smart text line paging | Yes | Byte paging | Yes |
| Multiple-file read | Yes | No | Yes |
| Image metadata / optional base64 | Yes | No | Yes |
| PDF text read | Yes | No | Optional `pypdf` provider |
| DOCX text read | Yes | No | Yes, stdlib OOXML |
| XLSX read | Yes | No | Yes, openpyxl + OOXML fallback |
| File info | Yes | No | Yes |
| mkdir / move | Yes | Basic list/write only | Yes |
| append writes | Yes | No | Yes |
| exact surgical replace | Yes | Yes | Yes |
| fuzzy edit fallback | Yes | No | Yes, explicit opt-in + dry-run |
| persisted tool-call history | Yes | Audit only | Yes, redacted JSONL |
| usage statistics | Yes | No | Yes |
| config read/edit UI | Yes | No | Yes, sanitized + whitelist |
| file preview UI | Yes | No | Basic Web Console preview |
| native Excel cell edit/write | Yes | No | Planned plugin |
| PDF write/modify | Yes | No | Planned plugin |
| DOCX create/edit | Yes | No | Planned plugin |
| URL read | Yes | No | Intentionally omitted from core (SSRF risk) |
| In-memory Python/Node/R execution | Yes | Shell can do it | Planned execution adapter |
| Remote hosted relay | Yes | Node Mesh/HTTP | Different architecture |
| Computer Use / UIA / WinAPI | No/core focus | Yes | Yes |
| Privileged OS broker | No/core focus | Yes | Yes |
| Agent runtime / Pi | No/core focus | Yes | Yes |
| Multi-node mesh | No/core focus | Yes | Yes |

## Deliberate non-copies

- URL fetching is not enabled by default because a privileged remote node would otherwise create an SSRF primitive.
- Preview/editor UI never rewrites the source file merely by opening or rendering it.
- `allowed_roots` remains separate from Shell policy; the UI explicitly describes that these are distinct security boundaries.
- Telemetry is not copied. Tool history stays on the node.
