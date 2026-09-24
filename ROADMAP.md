# Roadmap after 3.2

## 3.3 — Verified Computer Use
- Unified Desktop Graph source fusion/deduplication across HWND/UIA/OCR/vision.
- Windows Graphics Capture / DXGI backend.
- OmniParser or equivalent vision-grounding provider.
- Observe → act → observe → verify execution primitive.
- UIA pattern-specific actions (Value, Selection, Toggle, ExpandCollapse, Scroll).
- WTS-driven automatic Desktop Worker lifecycle in the active user session.

## 3.4 — Browser and Application Automation
- CDP events, screenshots, DOM snapshots, downloads and network inspection.
- Edge/Chrome profile discovery and managed debugging lifecycle.
- PowerPoint/Outlook COM adapters.
- LibreOffice UNO adapter for Linux/macOS/Windows.

## 3.5 — Enterprise MCP/Auth
- OAuth 2.1/OIDC resource-server provider.
- protected-resource metadata and audience validation.
- strict official MCP requirements/tier CI for supported protocol revisions.
- optional mTLS node-to-node credentials and short-lived mesh tokens.

## Scale / project quality
- SQLite/PostgreSQL storage provider for large fleets.
- OpenTelemetry traces/metrics.
- release signing/SBOM/reproducible packages.
- packaged Windows MSI/service + signed Desktop Worker.
- load/soak/chaos benchmarks and golden computer-use E2E fixtures.
