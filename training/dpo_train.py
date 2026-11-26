"""DPO fine-tuning with TRL + PEFT (LoRA) on citation-fidelity preference pairs.

!! NOT EXECUTED where this repo was generated (no GPU, no torch/trl, no network). !!
TRL's API changes between releases (e.g. `processing_class` vs `tokenizer`, DPOConfig
fields); pin versions in requirements-train.txt and adjust to the version you install.
Needs a GPU: a free Kaggle/Colab T4 is enough for a 0.5B-1.5B model with LoRA.

    python scripts/make_dpo_pairs.py --out data/dpo_pairs.jsonl    # (use a real LLM for chosen)
    python training/dpo_train.py --pairs data/dpo_pairs.jsonl --model Qwen/Qwen2.5-0.5B-Instruct

Log to W&B with `wandb login` and --report-to wandb. Evaluate before/after with the same
agent eval (scripts/run_agent_eval.py) pointed at the served model, and report regressions.
"""
import argparse
import json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", required=True)
    ap.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    ap.add_argument("--out", default="out/dpo-citation-lora")
    ap.add_argument("--epochs", type=float, default=2.0)
    ap.add_argument("--beta", type=float, default=0.1)
    ap.add_argument("--lr", type=float, default=5e-6)
    ap.add_argument("--report-to", default="none")
    a = ap.parse_args()

    from datasets import Dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import DPOConfig, DPOTrainer

    rows = [json.loads(l) for l in open(a.pairs) if l.strip()]
    tok = AutoTokenizer.from_pretrained(a.model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    def to_prompt(r):  # chat-format the prompt; chosen/rejected are the assistant completions
        return tok.apply_chat_template(
            [{"role": "system", "content": r["system"]}, {"role": "user", "content": r["prompt"]}],
            tokenize=False, add_generation_prompt=True,
        )

    ds = Dataset.from_list(
        [{"prompt": to_prompt(r), "chosen": r["chosen"], "rejected": r["rejected"]} for r in rows]
    )
    split = ds.train_test_split(test_size=0.1, seed=0)
    model = AutoModelForCausalLM.from_pretrained(a.model)
    cfg = DPOConfig(
        output_dir=a.out, num_train_epochs=a.epochs, beta=a.beta, learning_rate=a.lr,
        per_device_train_batch_size=2, gradient_accumulation_steps=4, logging_steps=5,
        report_to=a.report_to, max_length=1024,
    )
    trainer = DPOTrainer(
        model=model, args=cfg, train_dataset=split["train"], eval_dataset=split["test"],
        processing_class=tok,
        peft_config=LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, task_type="CAUSAL_LM",
                               target_modules=["q_proj", "k_proj", "v_proj", "o_proj"]),
    )
    trainer.train()
    trainer.save_model(a.out)


if __name__ == "__main__":
    main()
