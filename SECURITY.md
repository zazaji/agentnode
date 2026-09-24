# Security

AgentNode can intentionally execute administrator/root commands and can control an interactive desktop. Treat it as privileged remote-management software.

## Security boundaries

- **Auth**: static Bearer tokens are stored as SHA-256 hashes; raw tokens are shown only at creation time.
- **RBAC**: roles map to fine-grained scopes. `super` is the only wildcard role.
- **Explicit super mode**: a Super token alone is insufficient for unrestricted shell mode; local config must enable `shell.allow_super_mode` and the call must request `super_mode=true`.
- **File boundary**: canonical file/document paths remain under `files.allowed_roots`, including symlink resolution.
- **Shell boundary**: shell policy is independent. File roots are never described as a shell sandbox.
- **Job/session ownership**: non-super principals only inspect/control their own jobs and terminal/search sessions.
- **Mesh boundary**: trace/hop loop detection; peer secrets are referenced from environment/config and never returned by the API.
- **Desktop boundary**: observation and input use separate scopes; on Windows the interactive Desktop Worker is separate from the SYSTEM Core.
- **Document boundary**: document tools reuse FileManager path authorization and separate `document.read`/`document.write` scopes.
- **Browser boundary**: CDP is disabled by default and rejects non-loopback debugger endpoints unless `browser.allow_remote=true` is explicitly set. Never expose Chrome/Edge remote debugging directly to an untrusted network.
- **Office boundary**: Office COM is disabled by default and routes through the interactive Desktop Worker. Core fallback is off by default.
- **HTTP boundary**: `http.max_request_bytes` rejects oversized requests; Trusted Host validation protects the bound service from unexpected Host headers.
- **History/config**: tool history redacts token/API-key/password/secret-like fields; the Web Console receives sanitized configuration.

## Deployment rules

1. Bind to `127.0.0.1` by default.
2. For remote access, use TLS plus a VPN/private overlay or identity-aware reverse proxy.
3. Add the intended DNS name/IP to `http.trusted_hosts`; do not use `*` unless another trusted proxy fully enforces host validation.
4. Never expose a super-enabled node directly to the public internet.
5. Keep CDP on loopback. AgentNode should be the authenticated control boundary in front of it.
6. Run Desktop Worker in the intended logged-in user session; do not create an interactive SYSTEM desktop.
7. Keep `allow_super_mode: false`, `browser.enabled: false`, and `office.enabled: false` until each capability is intentionally required.
8. Rotate tokens and protect configuration/data with OS ACLs.
9. Treat screenshots, OCR, clipboard data, browser snapshots, Office documents and agent prompts as sensitive data.

## Risk model

- R0: observation/read-only diagnostics.
- R2: ordinary mutation.
- R3: system/application changes.
- R4: destructive or unrestricted privileged actions.
- R5: secret/credential access.

The current policy engine blocks/limits ordinary shell operations and requires the explicit Super path for unrestricted privileged execution. A future approval provider can require human approval for selected R4/R5 operations.

## MCP authentication note

Production remote MCP currently uses scoped static Bearer tokens. AgentNode 3.2 does **not** claim OAuth 2.1 resource-server conformance for that mode. The official conformance fixture is loopback-only and exists solely to test protocol behavior independently from production authentication.
