"""Experiment logging: always a local JSONL; also Weights & Biases when enabled.

Enable W&B with `pip install wandb`, `wandb login`, and DOCPILOT_WANDB=1. The W&B path is
a thin wrapper over wandb.init/log/finish and was not executed here (wandb not installed).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path


class ExperimentLogger:
    def __init__(self, name: str, config: dict | None = None, project: str = "docpilot",
                 path: str | Path = "results/runs.jsonl"):
        self.name, self.config, self.path = name, config or {}, Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.run = None
        if os.environ.get("DOCPILOT_WANDB") == "1":
            try:
                import wandb

                self.run = wandb.init(project=project, name=name, config=self.config)
            except Exception as e:  # missing package / not logged in: fall back to local only
                print(f"[expt] W&B disabled: {e}")

    def log(self, metrics: dict) -> None:
        rec = {"ts": time.time(), "run": self.name, "config": self.config, "metrics": metrics}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")
        if self.run is not None:
            self.run.log({k: v for k, v in metrics.items() if isinstance(v, (int, float))})

    def finish(self) -> None:
        if self.run is not None:
            self.run.finish()
