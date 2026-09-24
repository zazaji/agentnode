# Browser / Chrome DevTools Protocol

Enable explicitly:

```yaml
browser:
  enabled: true
  cdp_url: http://127.0.0.1:9222
  allow_remote: false
  timeout_s: 15
  max_snapshot_chars: 2000000
  max_screenshot_bytes: 8000000
```

## Current capabilities

- DevTools status/version;
- target/tab list;
- create/close tab;
- navigate target;
- structured DOM/text snapshot;
- page screenshot;
- CSS-selector click;
- CSS-selector text input;
- JavaScript `Runtime.evaluate`.

CDP is preferred to GUI clicking when available because it is structured and easier to verify. Browser snapshots and screenshots are size-capped before AgentNode returns them to remote callers.

## Security

Chrome/Edge remote debugging is a powerful unauthenticated local control surface. Keep it on loopback and let AgentNode provide the authenticated boundary. Non-loopback CDP endpoints are rejected unless `browser.allow_remote=true` is explicitly configured.
