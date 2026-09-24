# Windows Office COM

Enable explicitly:

```yaml
office:
  enabled: true
  use_desktop_worker: true
  allow_core_fallback: false
```

Install the Windows dependencies (`agentnode[windows,office]`) and Microsoft Office.

## Current native operations

### Excel
- range read/write;
- range formatting (bold/italic/font size/number format/alignment/wrap).

### Word
- full-text read;
- replace + save;
- insert table.

### PowerPoint
- extract slide text;
- append a title/body slide.

## Session model

A Windows service normally runs in Session 0. Office is user-profile and interactive-session sensitive, so AgentNode routes COM calls through the authenticated local Desktop Worker by default. If that worker is unavailable, operations fail rather than silently running Office from Session 0. `allow_core_fallback` is an explicit escape hatch for controlled deployments only.
