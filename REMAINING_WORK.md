# DocPilot: remaining work and commit plan

Work through the commits in order. Later steps depend on earlier ones: the evidence grader needs a real LLM (commit 6
before 7), and the final eval numbers need the real corpus (commit 8 before 9). Each commit lists what to do, the files it
will probably touch, the command to commit it, and when it counts as done.

Tick a box when its commit lands.

Commands are PowerShell, run from this folder.

---

## Setup (once)

The virtual environment `.venv` already exists with the dev requirements installed. Activate it in each new terminal:

```powershell
.venv\Scripts\Activate.ps1
git init -b main
```

Never commit `.venv/`, `.env`, API keys, model weights, or `out/` (DPO checkpoints). `.gitignore` excludes all of these.

---

## Commit 0: import the code

- [ ] Commit everything except the commit 2 files (the API fix and its tests) and this plan.
      `README.md` and `.gitignore` already contain the commit 2 edits; that's fine.

```powershell
git add .
git reset REMAINING_WORK.md docpilot/api.py tests/test_api.py requirements-dev.txt scripts/smoke_api.py loadtest/ask.js
git commit -m "chore: import DocPilot codebase"
```

## Commit 1: add this plan

- [ ] Add this file.

```powershell
git add REMAINING_WORK.md
git commit -m "docs: add remaining-work and commit plan"
```

Then create an empty GitHub repo and push: `git remote add origin <url>`, then `git push -u origin main`.

---

## Part A: needs your machine or accounts

### Commit 2: fix the API and test it over HTTP (item 1), DONE, ready to commit

The work is done (2026-11-26, Python 3.13, FastAPI 0.165).

- The original 33 tests passed.
- `POST /ask` and `/ask/stream` returned **422 on every request**. `from __future__ import annotations` in
  `docpilot/api.py` turned the `Request`/`AskRequest` annotations into strings that FastAPI couldn't resolve, because
  those names exist only inside `create_app()`. FastAPI then treated `request` and `req` as required query params.
  The fix removes that import and leaves a comment saying why.
- Added `tests/test_api.py` (8 tests: health, answer, abstain, 401, 422, stats, streaming, 429). It uses its own
  `DocPilot` instance, because the shared fixture's semantic cache would make `test_gateway` see a cache hit. 41 tests
  now pass.
- `smoke_api.py` passes against uvicorn. README updated.
- Added `httpx2` to `requirements-dev.txt`. Starlette 1.10's `TestClient` warns when it has to use plain `httpx`.
  Plain `httpx` stays as the fallback for older Starlette versions. The suite now runs with no warnings.
- Changed `http://localhost:8080` to `http://127.0.0.1:8080` in `smoke_api.py`, `loadtest/ask.js` and the README. On
  Windows `localhost` tries IPv6 `::1` first, but uvicorn listens on IPv4 only, so some clients stalled or failed.

```powershell
git add docpilot/api.py tests/test_api.py requirements-dev.txt scripts/smoke_api.py loadtest/ask.js
git commit -m "fix(api): resolve 422 on /ask caused by postponed annotations; add HTTP tests"
```

To rerun it yourself: `pytest -q`, then `uvicorn docpilot.api:create_app --factory --port 8080`, and in a second
terminal `python scripts/smoke_api.py http://127.0.0.1:8080`.

### Commit 3: real embeddings and cross-encoder rerank (item 2)

- [ ] `pip install -r requirements-full.txt`
- [ ] `$env:DOCPILOT_EMBEDDER = "st"`
- [ ] `python scripts/run_ablation.py --split test --tier paraphrase`, and again with `--tier lexical`.
- [ ] Fix anything that breaks. `SentenceTransformerEmbedder` and the cross-encoder have never run.
- [ ] Replace the README's retrieval table with the new numbers, keeping the bootstrap confidence interval.

Files: `docpilot/embeddings.py`, `docpilot/rerank.py`, `results/ablation_test_*.json|md`, `README.md`.

```powershell
git add docpilot results/ablation_test_* README.md
git commit -m "feat(retrieval): run real embeddings and cross-encoder rerank; update ablation"
```

Done when the ablation runs with `EMBEDDER=st` and the README shows those numbers.

### Commit 4: Qdrant and pgvector (item 3)

- [ ] `docker compose --profile qdrant --profile pgvector up -d qdrant pg`
- [ ] Run the retrieval comparison with `$env:DOCPILOT_STORE = "qdrant"`, then with `"pgvector"`. Use
      `DOCPILOT_QDRANT_URL=http://localhost:6333` and
      `DOCPILOT_PG_DSN=postgresql://postgres:postgres@localhost:5432/docpilot`.
- [ ] Fix `docpilot/stores.py` until both stores return the same top-k as the in-memory store on the same embedder.
- [ ] Write the comparison (hit@k, MRR, query latency) to `results/store_comparison.md`.

```powershell
git add docpilot/stores.py docker-compose.yml results/store_comparison.md README.md
git commit -m "fix(stores): get Qdrant and pgvector working; add store comparison"
```

### Commit 5: stop multi-part questions pulling in off-topic chunks (known weakness)

- [ ] Reproduce the bug: "roll back a Deployment and check rollout progress" returns a PostgreSQL sentence.
- [ ] Likely fix: apply the topic filter (`infer_topic`) to each sub-question from `split_subquestions` in
      `docpilot/query.py`, and drop chunks whose rerank score falls below a floor before merging, in `_n_retrieve`
      (`docpilot/agent.py`).
- [ ] Add that question as a regression test.

Files: `docpilot/query.py`, `docpilot/agent.py`, `tests/test_text_and_retrieval.py`.

```powershell
git add docpilot/query.py docpilot/agent.py tests/test_text_and_retrieval.py
git commit -m "fix(retrieval): filter off-topic chunks per sub-question in multi-part queries"
```

### Commit 6: connect a real LLM (item 5, part 1)

- [ ] Point `DOCPILOT_LLM_BASE_URL` (plus `DOCPILOT_LLM_API_KEY` and `DOCPILOT_SMALL_MODEL`/`DOCPILOT_LARGE_MODEL`) at an
      OpenAI-compatible endpoint. Keep the values in `.env`, never in code.
- [ ] Run `python -m docpilot ask "..."` and fix whatever breaks in `docpilot/llm.py` or `docpilot/gateway.py`.
- [ ] Add a `.env.example` with variable names only, no values.

```powershell
git add docpilot/llm.py docpilot/gateway.py .env.example
git commit -m "feat(llm): run agent against a real OpenAI-compatible model"
```

### Commit 7: replace the word-overlap evidence grader (known weakness)

- [ ] Today `_n_grade` (`docpilot/agent.py:173`) uses `rerank.coverage`, which only counts word overlap. Because of that it
      false-abstains on paraphrases and answered "Who created Kubernetes?" with coverage 1.0.
- [ ] Replace it with an LLM sufficiency check ("does this context contain the answer? yes/no plus a short reason") or an NLI
      cross-encoder. Keep the lexical check as a cheap first pass if you like.
- [ ] Retune the threshold on the **dev** split only, then run test once.
- [ ] Add tests: "Who created Kubernetes?" must abstain, and "How can I keep credentials out of plain configuration?" must
      answer.

Files: `docpilot/agent.py`, `docpilot/rerank.py` (or a new `docpilot/grader.py`), `docpilot/prompts.py`,
`tests/test_guards_and_agent.py`.

```powershell
git add docpilot tests/test_guards_and_agent.py
git commit -m "feat(agent): replace lexical evidence grader with LLM/NLI sufficiency check"
```

---

## Part B: needs your judgment

### Commit 8: real corpus and 150+ hand-verified questions (item 9)

- [ ] Replace the 11 bundled docs in `data/corpus/` with real documentation, such as the Kubernetes docs (CC BY 4.0, so
      credit them) or the PostgreSQL docs (PostgreSQL License). Aim for a few thousand chunks.
- [ ] If the corpus is large, commit a download script (`scripts/fetch_corpus.py`) and gitignore the raw files instead of
      committing them.
- [ ] Write and **hand-check** 150+ questions in `data/eval/questions.jsonl`, mixing lexical, paraphrased, multi-hop and
      unanswerable ones. Keep the dev/test split.

```powershell
git add data scripts/fetch_corpus.py .gitignore docpilot/corpus.py
git commit -m "data: real documentation corpus and 150+ hand-verified eval questions"
```

### Commit 9: rerun every eval on the real setup (item 5, part 2)

- [ ] With the real LLM, real embeddings and the new corpus, run `run_ablation.py`, `run_agent_eval.py --split test`
      (plus the `--no-cascade`, `--no-cache` and `--no-topic-filter` runs) and `red_team.py`.
- [ ] Replace every number in the README and remove "stand-in model" caveats that no longer apply.

```powershell
git add results README.md
git commit -m "eval: rerun ablation, agent eval and red team with real LLM on new corpus"
```

### Commit 10: validate the LLM judge (item 10)

- [ ] Label about 50 answers yourself (correct / partially correct / wrong, plus whether each is grounded) in
      `data/eval/human_labels.jsonl`.
- [ ] Run the judge in `docpilot/evaluation/judge.py` on the same answers and report Cohen's kappa in
      `results/judge_agreement.md`. Add a confusion table and a few examples where you and the judge disagreed.

```powershell
git add data/eval/human_labels.jsonl docpilot/evaluation/judge.py results/judge_agreement.md README.md
git commit -m "eval: validate LLM judge against 50 human labels (Cohen's kappa)"
```

---

## Part C: production pieces

### Commit 11: shared rate limiter (known weakness)

- [ ] `RateLimiter` in `docpilot/security.py` keeps its token bucket in process memory, so each replica counts separately.
      Add a Redis-backed limiter (an atomic Lua script or `INCR` + `EXPIRE` per key and window), used when
      `DOCPILOT_REDIS_URL` is set and falling back to in-memory otherwise.
- [ ] Add a `redis` service to `docker-compose.yml` and a test showing two limiter instances share one budget.

```powershell
git add docpilot/security.py docpilot/api.py docpilot/config.py docker-compose.yml requirements-full.txt tests
git commit -m "feat(security): Redis-backed rate limiter shared across replicas"
```

### Commit 12: Langfuse export (item 8)

- [ ] Follow `docs/tracing.md`: wrap `Tracer.trace()` / `Trace.span()` so spans also go to Langfuse. Check whether you
      have SDK v2 or v3, because the APIs differ. Attach `prompt_tokens`, `completion_tokens` and `cost_usd`.
- [ ] Keep it optional, enabled only when the `LANGFUSE_*` env vars are set.

```powershell
git add docpilot/tracing.py requirements-full.txt docs/tracing.md
git commit -m "feat(tracing): optional Langfuse export"
```

### Commit 13: serving and quantization benchmark (item 4)

- [ ] On a GPU (a free Kaggle T4 works), serve the FP16, AWQ and GGUF variants as described in `docs/serving.md`.
- [ ] Run `scripts/bench_serving.py` and the agent eval for each variant. Save the results to `results/serving_*.json` and
      add a table (throughput, TTFT, p95, answer quality, VRAM) to the README.
- [ ] Commit no weights.

```powershell
git add results/serving_* docs/serving.md scripts/bench_serving.py README.md
git commit -m "bench: compare FP16, AWQ and GGUF serving on T4"
```

### Commit 14: DPO (item 6)

- [ ] Build preference pairs with the real LLM (`scripts/make_dpo_pairs.py`), then run `training/dpo_train.py`. Expect
      to adapt it to your TRL version, and pin the versions that worked in `requirements-train.txt`.
- [ ] Record before/after eval numbers. Checkpoints stay in `out/`, which is gitignored.

```powershell
git add scripts/make_dpo_pairs.py training/dpo_train.py requirements-train.txt results/dpo_*.md
git commit -m "train: DPO on generated preference pairs; pin TRL versions; record results"
```

### Commit 15: deploy and load test (item 7)

- [ ] Deploy to Cloud Run or a similar host (`docs/deploy.md`), with secrets in the platform's secret store.
- [ ] Run `k6 run loadtest/ask.js` against the live URL.
- [ ] Put the live URL and the measured p95 latency in the README.

```powershell
git add docs/deploy.md loadtest README.md
git commit -m "deploy: Cloud Run deployment and k6 load test results"
```

### Commit 16: blog post (item 11)

- [ ] Write `docs/blog.md` on what moved quality and what didn't. Cover the grader swap, the real embeddings vs the
      hashing baseline, rerank, quantization and DPO, with the numbers from the commits above. Link it from the README.

```powershell
git add docs/blog.md README.md
git commit -m "docs: write-up of what moved quality and what didn't"
```

---

## Known weaknesses: where each one is handled

| Weakness | Commit |
|---|---|
| Evidence grader uses word overlap (false abstains, "Who created Kubernetes?") | 7 |
| Multi-part questions pull in an off-topic chunk | 5 |
| Rate limiter is per process | 11 |
