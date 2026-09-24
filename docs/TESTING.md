# Testing

## Portable test suite

```bash
pip install -e '.[dev,documents,browser]'
pytest -q
python -m compileall -q src tests scripts
```

The 3.2.1 release contains 63 portable unit/integration tests in the supplied environment (including `test_mesh_coordinate.py`: fan-out, self-exclusion, unknown peers, partial failure, timeout, loop/hop guards, endpoint wiring) plus `test_32_features.py`.

## MCP conformance

GitHub Actions runs `.github/workflows/mcp-conformance.yml` using the official `@modelcontextprotocol/conformance` package. The strict gate is the server initialize scenario; the current active suite is also captured as an artifact for visibility.

## Windows smoke/E2E

Validate on a real Windows 11 machine:

1. Core runs under SYSTEM via SCM.
2. Desktop Worker runs in the current interactive user session.
3. UIA window enumeration/tree works for Explorer, Notepad and Settings.
4. Desktop screenshot works across high-DPI/multi-monitor layouts.
5. OCR recognizes a known fixture when OCR extras are installed.
6. Mouse/keyboard input reaches the selected user desktop.
7. Unified Desktop Graph contains HWND/UIA/OCR sources.
8. Standard token cannot use super mode or inspect another user's jobs/sessions.
9. Super mode can query/restart a disposable service when locally enabled.
10. Cancelling a background process kills child processes.
11. Office COM executes through Desktop Worker against Excel, Word and PowerPoint.
12. Desktop Worker outage fails Office calls rather than silently moving into Session 0.
13. Chrome/Edge CDP works with a loopback remote-debugging profile.
14. Two AgentNodes delegate with a node token and loop detection rejects A→B→A.

## Live 4-node fleet E2E (`scripts/remote/e2e_mesh_matrix.py`)

Validated against the real fleet (debian coordinator + zjdebian10 CT + ser117 public
node + win10 VM), all on 3.2.1:

- peers visibility at every node matches the configured `mesh.peers`;
- 8-case bidirectional delegation matrix (every ordered pair) returns the peer's
  `hostname` (ct-smb / cnet.ocome.net.cn / DESKTOP-AJOPF11 / debian);
- trace-id propagation end-to-end;
- coordinate fan-out from local to all peers (parallel), with an unknown peer
  (reported in `unknown`, others still run), and sequential mode;
- remote-originated coordinate (zjdebian10→[local,ser117], ser117→[local,zjdebian10,win10]);
- live loop protection: pre-loaded `hops` containing the target's own node_id →
  `400 mesh loop detected`; `hops` length beyond `mesh.max_hops` → `400 max hops exceeded`;
- headless degradation: remotes answer browser/desktop scopes with a graceful
  scope-required rejection rather than failing the node.

Result: 21/21 cases PASS.

## Linux/macOS smoke

Use `scripts/smoke-posix.sh`; additionally validate platform permission behavior (Wayland/AT-SPI on Linux, Accessibility/Screen Recording on macOS where desktop backends are configured).
