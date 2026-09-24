# AgentNode 3.2 Test Report

## 3.2.1 update (mesh coordination + multi-node fleet E2E)

Version 3.2.1 adds in-product autonomous coordination to the mesh and was validated on a live 4-node fleet.

- Unit/integration tests: **63 passed** (55 at 3.2.0 + 8 new `test_mesh_coordinate.py` cases covering coordinate fan-out, self-exclusion, unknown peers, partial failure, timeout, sequential mode, loop/hop guards, and endpoint wiring); `compileall` PASS.
- Dist rebuilt: `agentnode-3.2.1-py3-none-any.whl` + `agentnode_3.2.1_all.deb` (secret scan clean: no config/env/token files, no worker_secret/apigate values).
- Live fleet E2E (`scripts/remote/e2e_mesh_matrix.py`), **21/21 PASS** across debian + zjdebian10 + ser117 + win10 (see `docs/TESTING.md` for the full matrix).
- Loop protection re-verified on the wire: pre-loaded `hops` hitting the target's own node_id → `400 mesh loop detected` (at both local and remote entry points); `hops` beyond `mesh.max_hops` → `400 max hops exceeded`.
- CLI verified live: `agentnode mesh-coordinate --peer zjdebian10 --peer ser117 --command hostname` returned both hostnames with a shared trace_id.

### Fleet deployment notes (3.2.1)

- Deployment: zjdebian10 (Debian 13, apt .deb) and ser117 (Ubuntu 24.04, venv+wheel because apt pydantic is v1) both `systemctl enabled + active` as boot services.
- Topology: full bidirectional legs with direct LAN routes where the hairpin NAT allows, and reverse-SSH tunnel legs otherwise (local `-L 18763`, `-R 18764/18765/18766/18767`; user-scope systemd units, Linger, `enabled + active`). Full detail in `docs/DEPLOYMENT.md`.

## Summary

Release candidate validation completed in the provided Linux container, followed by a two-node E2E acceptance run (debian host + Windows 10 VM on libvirt NAT).

- Unit/integration tests: **55 passed** (53 original + 2 new MCP regression tests)
- Python bytecode compilation: **PASS**
- Editable package build/install without build isolation: **PASS**
- CLI import/version/route registration: **PASS**
- YAML parsing for config and GitHub Actions workflows: **PASS**
- Wheel build: **PASS** (`agentnode-3.2.0-py3-none-any.whl`)
- Application route smoke: **82 routes**, required 3.2 routes present
- Basic native-shell benchmark: **20 runs / ~0.076 s** in the release container

## Two-node E2E acceptance (scripts/acceptance_e2e.py)

Topology: debian host node (`127.0.0.1:8765`, node_id `debian`) + Windows 10 VM node (`192.168.122.4:8765`, libvirt NAT `192.168.122.1/24`). Static scoped Bearer tokens (operator / super / node) synced across both nodes.

| Suite | Result |
| --- | --- |
| debian node (auth, RBAC, shell policy R0/R2/R4, super_mode, blocked fragments, code, files roundtrip/escape/traversal, searches, terminal, jobs+events+cancel+owner isolation, documents xlsx/docx/pdf, config redaction+editable whitelist, audit, services, processes, mesh delegates/peers/loop/unknown, http 413+untrusted Host) | **64 pass / 0 fail** |
| MCP HTTP (401 unauth, initialize, tools/list 40 tools, tools/call node_info, RBAC denied) + MCP stdio (SDK client subprocess) | **6 pass / 0 fail** |
| win10 node (same as debian, replacing pypdf client build with Windows-specific deep probes; boot-time service, RBAC, files from SYSTEM CWD, python codeexec, desktop graph, office, browser/CDP, bidirectional mesh) | **66 pass / 0 fail** |

**Final gate: 136 pass / 0 fail across all three suites.**

### Windows deep probes (win10 VM)

- desktop observe (super role; node role asserted 403), win32 window enumeration, UIA tree, unified graph (sources windows/uia/ocr) — PASS
- office COM capabilities via Desktop Worker (status/write/read-back) — PASS (with administrator+ RBAC)
- browser CDP status, tab enumerate, Runtime.evaluate, DOM snapshot, new/close tab — PASS (Chrome 154, `--remote-debugging-port=9222`)
- mesh delegate win10 → debian (trace_id, hostname) — PASS

### Linux host node: boot-time systemd service (debian)

The debian host node is now a real systemd service instead of a manual background process, auto-starts at boot, and stays callable from the mesh.

- Host facts: `PID 1 = systemd` (not containerized), user `zazaji` has `Linger=yes`, so a **user-scope** unit boot-starts with the user manager. Root/sudo is blocked in this session (NoNewPrivileges), so the unit lives at `~/.config/systemd/user/agentnode.service` with `WantedBy=default.target` rather than the root-unit path in `install-linux.sh`.
- Unit (User-level systemd service — a genuine daemon: `Type=simple`, `Restart=on-failure` + `RestartSec=3`): `WorkingDirectory=/home/zazaji/projects/agentnode`, `EnvironmentFile=-~/.config/agentnode/service.env`, `ExecStart=<venv>/python -m agentnode serve --config config.yaml`.
- `service.env` (0600, same mesh-token contract the Windows service uses) provides `AGENTNODE_PEER_WIN10_TOKEN`, injected via the `EnvironmentFile` — verified end-to-end.
- Verified:
  - `systemctl --user is-enabled agentnode` → `enabled`; `loginctl show-user zazaji` → `Linger=yes` (boot-time start; a full reboot test is pending outside this sandboxed session).
  - `systemctl --user restart agentnode` → recovers to `active`, listens on `0.0.0.0:8765` again (port freed after the old manual process was stopped).
  - **debian service → win10** mesh delegate returns `DESKTOP-AJOPF11` (outbound peer token came from the service `EnvironmentFile`).
  - **win10 → debian service** mesh delegate returns `debian` (the new service is callable as a mesh receiver over the network).

### pi agent model wiring (user acceptance item)

- Custom provider `test-gateway` configured on win10 (`~/.pi/agent/models.json` + `agent.runtimes.pi` + `llm.profiles` in `config.yaml`): endpoint `http://192.168.122.1:10003/v1`, model `c_glm`, vision enabled, context 256k, output 32k, apikey via `TEST_GATEWAY_API_KEY`.
- Invocation E2E: `POST /api/v1/agent` → `state=succeeded`, `runtime=pi`, 40 rpc events, final assistant reply exactly `AGENT-RUN-OK`.
- Vision E2E: generated a marker image (`AN-VISION-42` text) on the VM via PowerShell/System.Drawing, pi agent read tool opened the PNG and `c_glm` replied exactly `AN-VISION-42`.

### Bugs found and fixed during E2E

This session’s two-node + boot-service work surfaced and fixed additional defects:

- Node-role mesh delegation wrongly 403’d: a delegate forwarded by a peer arrives with a node token and only the node role, but `check_shell` demanded `shell.write` (which node lacks). Router now stamps `trace_id`/`hops` on the forwarded request and `check_shell` treats a delegated request as authorized by `mesh.delegate` — so node tokens can delegate (TESTING.md #14) while direct node shell stays denied (403, required by the acceptance target).
- Windows service process model: `sc.exe ... start= auto obj= LocalSystem` starts with `CWD=C:\Windows\system32` and a stripped PATH (no `python3`, no user paths). Fixed with a `run_core.py` wrapper (chdir to the app dir, load optional `service.env` for mesh peer tokens / PATH, spawn the real server with logs to `serve.log`, wait as service main) and a `CodeExecutor.sys.executable` fallback for interpreter resolution.
- `sc stop` terminates only the `run_core.py` parent; the spawned child can linger and keep the port. Installers keep failure-recovery (`sc.exe failure ...`) and this report treats a full machine restart as the authoritative reboot test.
- Restart interface on this win10 guest: ACPI `virsh reboot` was not honored (guest ignores it), but `virsh reset` (QEMU machine reset, no guest cooperation needed) full-rebooted the VM and the boot-time service recovered the node in ~20 s (validated by the guest `boot_time` advancing to the reset moment). `virsh destroy` + `start` remains the fallback.
- Product-API reboot (`shutdown /r`, an R4 command) requires explicit super mode; the win10 node is deployed with `shell.allow_super_mode: false` for safety, so the API deliberately refuses it — enabling that switch is the documented way to reboot through the product interface.
- File policy on a Windows service: a bare `C:\` allowed root plus relative roots resolve against `System32`; the VM config now pins explicit `allowed_roots` and uses a stable service working directory.

Earlier findings retained below.

- FastAPI had no OS-error exception mapping (500s on expected 4xx): added handlers mapping `PermissionError→403`, `FileNotFoundError→404`, `FileExistsError→409`, `KeyError/ValueError/RuntimeError→400`, `TimeoutError→504`.
- openpyxl read_only workbooks never closed → Windows file handle leak blocked `os.replace` (HTTP 403 拒绝访问 on xlsx append): added `wb.close()` in `finally` across documents manager and files.py.
- Chrome 111+ rejects CDP websocket handshakes carrying an Origin header (HTTP 403 handshake): client-side `suppress_origin=True` in browser/cdp.py.
- `shutil.which('python')` resolving to the Microsoft Store alias stub (exit 9009, no output): CodeExecutor falls back to `py` launcher / `sys.executable`; LANGS candidates extended.
- `asyncio.create_subprocess_exec('pi')` fails on Windows (WinError 2, extensionless script): AgentRuntimeManager resolves the executable via `shutil.which` (finds `pi.cmd`) and injects configured args after `--mode rpc`.
- FastMCP DNS-rebinding protection broke loopback/TestClient requests (421 Invalid Host): explicit `TransportSecuritySettings` mirroring `http.trusted_hosts` (exact and `:*` forms); bare `/mcp` served via explicit StarletteRoute (GET/POST/DELETE) avoiding the Starlette Mount 307 redirect; stdio transport grants a local administrator principal (`AGENTNODE_MCP_TRANSPORT=stdio`).
- pywinauto `Desktop().window(title_re=...)` raises `ElementAmbiguousError` when several top-level windows match, silently returning empty results: `WindowsUIA._match()` now resolves deterministically to the first matching window (find/invoke/tree).

## Tested capability areas

### Core / security
- token hashing and role/scope authorization;
- explicit Super mode policy;
- file allowed-root/path escape protection;
- job ownership and restart recovery;
- event cursors and audit/history redaction;
- config editable-key whitelist and sanitization;
- Mesh hop/loop behavior;
- HTTP request-size rejection (413);
- Trusted Host-compatible test configuration.

### Desktop Commander parity
- smart file reads and pagination;
- DOCX/XLSX container reads/search;
- search sessions and pagination;
- fuzzy edit + dry-run behavior;
- terminal cursor/output ownership;
- tool history/usage;
- code execution;
- native Linux subprocess integration.

### 3.2 documents
- XLSX create, range write/read and row append;
- DOCX create/read/replace;
- PDF merge/read;
- document permission enforcement;
- document routes registered in the application.

### 3.2 browser/CDP
- disabled-by-default enforcement;
- non-loopback CDP rejection unless explicitly enabled;
- structured action generation for click/type/screenshot;
- Browser routes registered in the application.

### 3.2 Unified Desktop Graph
- window/UIA graph construction;
- stable graph hashing;
- OCR-provider shape normalization;
- source and containment/fusion structures.

### 3.2 Office/session model
- Office disabled-by-default behavior;
- Office Manager prefers Desktop Worker on Windows;
- Desktop Worker failure does not silently fall back to Session 0 unless explicitly configured;
- Office API routes registered.

## MCP conformance

The repository contains `.github/workflows/mcp-conformance.yml`, using the official `@modelcontextprotocol/conformance` runner. The strict CI gate exercises server initialization against a loopback-only raw MCP fixture; the current active suite is also executed for visibility and uploaded as an artifact.

Local validation (project venv, `mcp` SDK 1.30): streamable-HTTP server at `/mcp` exercised E2E — unauthenticated POST rejected 401, `initialize`/`tools/list`/`tools/call` succeed over loopback, `tools/list` returns all 40 tools, tool call respects RBAC (403 `scope required: shell.write` surfaced as `isError` content); stdio transport exercised with the official SDK client (initialize → list_tools → call node_info). Unit regression tests appended (`tests/test_32_features.py`). The external `@modelcontextprotocol/conformance` runner is still CI-only.

Production remote MCP uses scoped static Bearer tokens in 3.2. This release therefore does not claim full OAuth 2.1 MCP resource-server conformance.

## Platform-specific validation still required

Two-node E2E covered the Windows interactive-session paths listed below plus the boot-time service on a real Windows 10 VM. Remaining items for future CI coverage:

- Windows SCM / LocalSystem boot-time service: **validated** on win10 (sc.exe `start= auto obj= LocalSystem`; node reachable from the debian host after a full machine restart via `virsh reset`; CWD anchored to the app dir). Still not exercised in automated CI.
- Linux host-node boot-time service: **validated** as a user-scope systemd unit (`systemctl --user` enabled + active, `Linger=yes`, restart self-heals, bidirectional mesh callable) — full host reboot outside this sandboxed session still pending.
- Windows OCR / RapidOCR model runtime where configured (BitBlt capture returns 拒绝访问 in the current service context, so screenshot-dependent paths are env-constrained);
- macOS Accessibility/launchd behavior.

## Environment note

A global `pip check` in the supplied container reports an unrelated pre-existing `moviepy`/`Pillow` conflict. AgentNode itself built and installed successfully. The release validation therefore checks AgentNode's declared direct requirements independently rather than treating unrelated environment conflicts as a project failure.
