# Tracing

Implemented: local JSONL traces (`docpilot/tracing.py`), one line per request with per-node spans and attributes;
`python scripts/trace_report.py results/traces_test.jsonl` gives per-node p50/p95, abstain reasons and cost.

Not implemented: Langfuse / OpenTelemetry export. To add it, wrap `Tracer.trace()` / `Trace.span()` so each span is also
sent to the Langfuse SDK (check the SDK version's current API — it changed between v2 and v3) and attach
`prompt_tokens`, `completion_tokens` and `cost_usd` (already present in the `generate` span attributes).
