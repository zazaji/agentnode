# Unified Desktop Graph

The graph is a semantic desktop snapshot consumed by agents instead of forcing every step to reason from pixels.

Node kinds currently include:
- `window`: Win32 HWND/top-level window;
- `uia`: Windows UI Automation element;
- `ocr`: OCR text region.

Edges currently represent UI containment. Every snapshot has a deterministic `graph_hash` suitable for change detection. Future providers may add vision-grounded elements and cross-source equivalence/spatial edges without changing the endpoint.
