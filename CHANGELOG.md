# Changelog

## 3.3.0

### Added
- Task relay (转交) with auxiliary-node gating: `mesh.helper_key` determines
  which nodes serve `/api/v1/mesh/forward` (header `X-AgentNode-Helper-Key`,
  constant-time compared; no key → node refuses to be a helper).
- Forward policy `mesh.forward_policy`: `mode: off|offload|distribute`,
  `offload_after` (hand off when in-flight load exceeds N), `max_forwards`
  (relay budget / max hops).
- Per-task `forwardable` flag: a relayed task marked `forwardable: false` is
  always executed locally (cannot be re-transferred); an origin may still hand
  it off once with an explicit `target`.
- Upstream/loop avoidance: every hop appends itself to `hops`; forward targets
  and `coordinate` fan-out both exclude path members, so a task (or sub-task)
  can never round-trip back to an upstream node; explicit targets already on
  the path are refused.
- `agentnode mesh-forward` CLI subcommand (key, target, policy override,
  `--no-forwardable`); mesh relay endpoint `POST /api/v1/mesh/forward`.
- Web Console runtime configuration editor: the Config tab renders a type-aware
  editor (text/number/boolean/enum/secret fields) for every runtime-editable key,
  marks restart-only settings (`host`, `port`, `data_dir`, `http.*`, `auth.*`,
  `mesh.peers`, ...), and shows a redacted raw JSON view. Saving writes the YAML
  atomically with a `.bak` snapshot and applies the change live without a restart.
- `mesh.helper_key` is now runtime-editable (secret-masked in the view; a new key
  takes effect immediately on relay gating). Invalid keys/values — including an
  unknown `mesh.forward_policy.mode` — are rejected with 400 instead of accepted.
- 6 config-editor unit/integration tests (redaction, round-trip persistence,
  invalid 400s, RBAC scopes, live helper-key switch, console serving the editor).
- 21 unit/integration tests for the relay feature; version surface updated to 3.3.0.

### Changed
- Upstream exclusion compares the visited `hops` path against each peer's declared
  `peers.<name>.node_id` (not its local config key). A peer can be named anything,
  so loop-avoidance must recognise the node the peer *is* before handing a task
  back to it. Live-fleet test caught the name/mismatch and it is fixed + regression-tested.

## 3.2.0
### Added
- Rich document plugin: XLSX range read/write/create/append, DOCX read/create/replace, PDF read/merge.
- Independent `document.read` / `document.write` scopes.
- Chrome/Edge DevTools Protocol adapter with target discovery, navigation, DOM/text snapshot, screenshot, CSS-selector click/type, tab create/close and JS evaluation.
- Independent `browser.read` / `browser.write` scopes and disabled-by-default CDP configuration.
- Windows Office COM adapter for Excel, Word and PowerPoint with `office.read` / `office.write` scopes; Windows service deployments route COM to the interactive Desktop Worker by default.
- Unified Desktop Graph combining Win32 windows, UIA elements and OCR regions.
- Web Console panels for Desktop Graph, Browser and Documents; inline image file preview.
- Official MCP conformance GitHub Actions workflow and loopback-only fixture.
- HTTP request-size limiting, Trusted Host middleware and security headers.
- 3.2 feature regression tests.

### Changed
- Version surface updated to 3.2.0.
- Administrator/operator/developer/desktop scopes extended for the new capability families.
- Architecture documentation now formalizes API-first/browser/Office execution before GUI fallbacks.

### Security
- Browser CDP and Office COM are disabled by default.
- Document operations reuse the FileManager path boundary rather than implementing a second path policy.
- MCP conformance fixture is isolated from the production authenticated endpoint and binds only to loopback.

## 3.2.0 – deployment hardening (post-rc)

### Fixed
- Node-role mesh delegation: a delegated request forwarded by a peer (node token, node role) was rejected with 403 because `check_shell` demanded `shell.write`, which the node role lacks. The mesh router now stamps `trace_id`/`hops` on forwarded requests and `check_shell` authorizes delegated calls via `mesh.delegate` while continuing to deny direct node shell. Loop detection and hop limits are preserved.
- Code execution under Windows LocalSystem services: a service process starts with a stripped PATH, so `shutil.which('python')` could miss the runtime. `CodeExecutor` now falls back to `sys.executable` for the Python target.
- File policy on a Windows service: the service CWD is `C:\Windows\system32`, so bare `C:\`/relative `allowed_roots` mis-apply. Deployment now pins explicit `allowed_roots` and anchors a stable service working directory.

### Changed
- `scripts/install-windows.ps1` now installs the core as a boot-time Windows service (`sc.exe create AgentNode ... start= auto obj= LocalSystem`) via a generated `run_core.py` wrapper that chdir()s to the app directory, loads an operator-editable `service.env` (mesh peer tokens / PATH), and captures logs to `serve.log`. The Desktop Worker remains a per-logon task by design (interactive-session UI needs a logged-in user).
- `scripts/install-linux.sh` now sets `WorkingDirectory` and an optional `EnvironmentFile=/etc/agentnode/service.env` on the boot-time systemd unit, so relative data paths and mesh peer tokens work regardless of the unit’s start context.
- `scripts/uninstall-windows.ps1` also removes the generated wrapper/env/log artifacts while retaining configuration and data.

## 3.1.0
See the prior Desktop Commander parity release notes and `docs/DESKTOP_COMMANDER_PARITY.md`.
