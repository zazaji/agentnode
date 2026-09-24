from __future__ import annotations
import json, time
from collections import Counter
from pathlib import Path
from threading import Lock
from typing import Any

class ToolHistory:
    """Persistent, bounded JSONL tool-call history.

    Inspired by Desktop Commander's persisted recent-tool-call history, but kept
    local-only and telemetry-free. Sensitive payloads are redacted before write.
    """
    def __init__(self, path: str | Path, max_records: int = 5000):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_records = max_records
        self._lock = Lock()

    @staticmethod
    def _redact(value: Any, key: str = "") -> Any:
        sensitive = {"token", "authorization", "api_key", "apikey", "secret", "password", "worker_secret"}
        if any(s in key.lower() for s in sensitive):
            return "***"
        if isinstance(value, dict):
            return {k: ToolHistory._redact(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [ToolHistory._redact(v, key) for v in value[:100]]
        if isinstance(value, str) and len(value) > 4000:
            return value[:4000] + "…"
        return value

    def record(self, tool: str, actor: str, args: Any, result: Any = None, error: str | None = None,
               duration_ms: int | None = None, source: str = "rest") -> None:
        row = {
            "ts": time.time(), "tool": tool, "actor": actor, "source": source,
            "args": self._redact(args), "result": self._redact(result),
            "error": error, "duration_ms": duration_ms,
        }
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            self._compact_if_needed()

    def _compact_if_needed(self) -> None:
        try:
            if self.path.stat().st_size < 20_000_000:
                return
            lines = self.path.read_text("utf-8", errors="replace").splitlines()[-self.max_records:]
            self.path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        except OSError:
            pass

    def recent(self, limit: int = 100, tool: str | None = None, actor: str | None = None) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in reversed(self.path.read_text("utf-8", errors="replace").splitlines()):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if tool and r.get("tool") != tool:
                continue
            if actor and r.get("actor") != actor:
                continue
            rows.append(r)
            if len(rows) >= min(max(limit, 1), 1000):
                break
        return rows

    def usage(self, actor: str | None = None) -> dict[str, Any]:
        rows = self.recent(self.max_records, actor=actor)
        by_tool = Counter(r.get("tool", "unknown") for r in rows)
        failures = sum(1 for r in rows if r.get("error"))
        durations = [r["duration_ms"] for r in rows if isinstance(r.get("duration_ms"), (int, float))]
        return {
            "calls": len(rows), "failures": failures,
            "failure_rate": round(failures / len(rows), 4) if rows else 0,
            "by_tool": dict(by_tool.most_common()),
            "avg_duration_ms": round(sum(durations) / len(durations), 2) if durations else None,
        }
