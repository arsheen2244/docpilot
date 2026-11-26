"""Minimal tracing: one JSON line per request with per-node spans, latency and attributes.

This is local and dependency-free. It is NOT a Langfuse/OpenTelemetry integration; see
docs/tracing.md for how to export these same spans to Langfuse.
"""
from __future__ import annotations

import json
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


class SpanHandle:
    def __init__(self, rec: dict):
        self._rec = rec

    def set(self, **attrs) -> None:
        self._rec["attrs"].update(attrs)


class Trace:
    def __init__(self, name: str, attrs: dict):
        self.id = uuid.uuid4().hex[:16]
        self.name = name
        self.attrs = dict(attrs)
        self.spans: list[dict] = []
        self._t0 = time.perf_counter()
        self.duration_ms = 0.0

    @contextmanager
    def span(self, name: str, **attrs):
        rec = {"name": name, "start_ms": (time.perf_counter() - self._t0) * 1000, "attrs": dict(attrs)}
        self.spans.append(rec)
        try:
            yield SpanHandle(rec)
        except Exception as e:
            rec["attrs"]["error"] = repr(e)
            raise
        finally:
            rec["dur_ms"] = (time.perf_counter() - self._t0) * 1000 - rec["start_ms"]

    def to_dict(self) -> dict:
        return {
            "trace_id": self.id,
            "name": self.name,
            "duration_ms": round(self.duration_ms, 3),
            "attrs": self.attrs,
            "spans": [
                {**s, "start_ms": round(s["start_ms"], 3), "dur_ms": round(s.get("dur_ms", 0.0), 3)}
                for s in self.spans
            ],
        }


class Tracer:
    def __init__(self, sink: str | Path | None = None):
        self.sink = Path(sink) if sink else None
        if self.sink:
            self.sink.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def trace(self, name: str, **attrs):
        t = Trace(name, attrs)
        try:
            yield t
        finally:
            t.duration_ms = (time.perf_counter() - t._t0) * 1000
            if self.sink:
                with self.sink.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(t.to_dict(), default=str) + "\n")
