# AgentNode 3.2 Release Notes

## Theme

**Structured control before pixel control.**

3.2 moves AgentNode from a strong Desktop Commander-style execution node toward an application-aware computer-use runtime. Browser, Office and rich documents now have native structured adapters, while the Unified Desktop Graph gives agents a common semantic view of windows/UIA/OCR.

## Highlights

- Rich XLSX/DOCX/PDF plugin with guarded write operations.
- Browser/CDP: tabs, navigation, DOM/text snapshot, screenshot, CSS click/type, JS evaluate.
- Windows Office COM: Excel, Word and PowerPoint.
- Office execution routed to the interactive Desktop Worker by default.
- Unified Desktop Graph: HWND + UIA + OCR, stable hash and evidence edges.
- Web Console panels for Browser, Documents/Office and Desktop Graph.
- HTTP request limits, Trusted Host and security headers.
- Official MCP conformance workflow integration.
- 55 local unit/integration tests passing in the release environment.

## Deployment (boot-time service)

The core node starts at machine boot on both platforms — no interactive logon required:

- **Windows**: `scripts/install-windows.ps1` registers `AgentNode` as a native service (`sc.exe create ... start= auto obj= LocalSystem`). A generated `run_core.py` changes to the app directory, loads `service.env` (mesh peer tokens / PATH), and captures logs to `serve.log`. The Desktop Worker remains a per-logon task because UI automation needs an interactive session; the core service itself needs none.
- **Linux**: `scripts/install-linux.sh` registers a `multi-user.target` systemd unit with a fixed `WorkingDirectory` and optional `EnvironmentFile` for mesh peer tokens.

See `docs/DEPLOYMENT.md` and `TEST_REPORT.md` for the full reboot-connectivity validation (win10 VM cold boot → node reachable, RBAC intact, bidirectional mesh delegate working).

## Upgrade from 3.1

Existing 3.1 configuration remains compatible. New sections are optional:

```yaml
http:
  max_request_bytes: 8000000
  trusted_hosts: ["127.0.0.1", "localhost"]

browser:
  enabled: false
  cdp_url: http://127.0.0.1:9222
  allow_remote: false

office:
  enabled: false
  use_desktop_worker: true
  allow_core_fallback: false
```

For LAN/VPN access, add the node's intended DNS name/IP to `http.trusted_hosts` and terminate TLS at AgentNode or a trusted reverse proxy.

## Optional installs

```bash
pip install -e '.[mcp,documents,browser]'
# Windows deep-operation node:
pip install -e '.[mcp,documents,browser,windows,office,ocr]'
```

## Compatibility note

Production MCP still uses AgentNode's scoped static Bearer tokens. 3.2 integrates the official conformance framework but does not claim OAuth 2.1 resource-server tier conformance. That work is explicitly planned rather than hidden behind a compatibility label.
