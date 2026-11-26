"""Smoke-test a running DocPilot server:  python scripts/smoke_api.py http://127.0.0.1:8080 [API_KEY]"""
import json
import sys
import urllib.request

base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"
key = sys.argv[2] if len(sys.argv) > 2 else ""


def call(path, body=None):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json", "X-API-Key": key})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


print("health:", call("/health"))
r = call("/ask", {"question": "What is the default isolation level in PostgreSQL?"})
assert r["answer"] and not r["abstained"], r
r2 = call("/ask", {"question": "What is the default port of MongoDB?"})
assert r2["abstained"], r2
print("ok: answered a covered question and abstained on an uncovered one")
