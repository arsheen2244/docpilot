import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import bench_serving  # noqa: E402


class FakeLLM(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        time.sleep(0.05)  # fake prefill -> TTFT ~50 ms
        for i in range(10):
            self.wfile.write(f'data: {json.dumps({"choices": [{"delta": {"content": f"t{i} "}}]})}\n\n'.encode())
            self.wfile.flush()
            time.sleep(0.01)
        self.wfile.write(b"data: [DONE]\n\n")


def test_bench_measures_ttft_and_throughput():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeLLM)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        out = bench_serving.run(f"http://127.0.0.1:{srv.server_port}/v1", "fake", 4, 8, 16)
    finally:
        srv.shutdown()
    assert out["requests_ok"] == 8 and out["errors"] == 0
    assert 40 <= out["ttft_ms_p50"] <= 400
    assert out["aggregate_tokens_per_s"] > 0


def test_dpo_pairs_are_well_formed(tmp_path):
    import subprocess
    out = tmp_path / "p.jsonl"
    root = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, str(root / "scripts" / "make_dpo_pairs.py"), "--out", str(out)],
                   check=True, cwd=root, capture_output=True)
    rows = [json.loads(l) for l in out.read_text().splitlines()]
    assert len(rows) >= 10
    for r in rows:
        assert r["chosen"] != r["rejected"] and "[" in r["chosen"] and r["prompt"].startswith("<context>")
