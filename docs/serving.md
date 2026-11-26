# Serving and quantization experiment (not run in the repo's build environment)

Goal: report quality, TTFT and throughput for FP16 vs AWQ vs GGUF of the *same* model on the *same* GPU.
`scripts/bench_serving.py` is tested against a fake streaming server; the vLLM commands below are untested here.

1. Rent/borrow one GPU (Kaggle T4 is enough for 1.5B). Pick a model that has official quantized variants
   (e.g. a Qwen2.5 Instruct size with `-AWQ` / `-GPTQ-Int4` repos — confirm exact repo names on the Hub).
2. Serve each variant, one at a time, same `--max-model-len`:
   - FP16:  `vllm serve <model> --max-model-len 4096`
   - AWQ:   `vllm serve <model>-AWQ --quantization awq --max-model-len 4096`
   - GGUF:  `llama-server -m <model>-Q4_K_M.gguf -c 4096 --port 8000` (llama.cpp, OpenAI-compatible)
3. For each: `python scripts/bench_serving.py --base-url http://localhost:8000/v1 --model <name> --concurrency 1|4|16 --requests 64 --label <variant>`
4. Quality: point DocPilot at each server (`DOCPILOT_LLM_BASE_URL`, `DOCPILOT_SMALL_MODEL`) and run
   `python scripts/run_agent_eval.py --split test`. Report answer rate, citation accuracy and abstention per variant.
5. Table to publish: variant | VRAM | TTFT p50/p95 | tok/s @1,4,16 | answer rate | cites-gold | correct abstention.
   Keep GPU, driver, vLLM version, prompt and max_tokens identical, and say so.
