# Models, scanners and generation

PatchLens 0.2 includes runnable optional integrations. The core demo still runs with NumPy alone. All commands below run locally; model downloads require the explicit `--allow-download` switch. The browser only displays saved results.

## Install the tested neural stack

Use Python 3.12 in a fresh virtual environment. For the CPU build tested for this release:

```bash
python -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install '.[train]'
```

The tested stack is PyTorch 2.8.0+cpu, Transformers 4.56.2 and PEFT 0.17.1. `requirements-neural-lock.txt` records the resolved neural environment. CUDA and Apple MPS are selectable but were not validated here. A checkpoint's licence and hardware requirements must be assessed before reuse. Model weights are not redistributed in this repository.

## Train an encoder classifier

Use a local, complete encoder checkpoint in safetensors format with its tokenizer. BERT/RoBERTa-style encoders expose the `query,value` target modules used below. Other architectures need their own target names. Encoder-decoder and generative decoder training are outside this classifier track. A new binary task head is allowed during training and its missing keys are recorded; missing backbone weights are rejected.

```bash
# Frozen representation baseline; only the task head learns.
patchlens train-hf --model models/encoder --mode frozen --contrastive-weight 0 --positive-weight 1 --epochs 3 --output runs/hf-frozen

# Ordinary full supervised fine-tuning.
patchlens train-hf --model models/encoder --mode supervised --contrastive-weight 0 --positive-weight 1 --epochs 3 --output runs/hf-supervised

# Full contrastive fine-tuning with an unweighted classification term.
patchlens train-hf --model models/encoder --mode supervised --contrastive-weight 0.3 --positive-weight 1 --epochs 3 --output runs/hf-contrastive

# Parameter-efficient security-weighted contrastive training.
patchlens train-hf --model models/encoder --mode lora --target-modules query,value --rank 8 --contrastive-weight 0.3 --positive-weight 3 --epochs 3 --output runs/hf-lora
```

Keep the encoder, tokenizer, seed, data and hyperparameters controlled across a study. Comparing full training against LoRA changes both the objective and adaptation method; it is not an isolated loss ablation. For a LoRA-only ablation, hold `--mode lora` fixed while changing loss weights.

Training uses only the training split. Each minibatch contains complete vulnerable/corrected pairs plus their authored label-preserving views. The view is the contrastive positive; opposite-label samples are negatives, and other same-label samples are masked. Positive-class weighting multiplies per-example classification loss; it does not directly minimize empirical FNR. Fixed epoch counts are declared before training. Truncated example IDs are recorded for inspection.

Every run writes `training.json`, `history.json`, `predictions.jsonl`, `embeddings.json` and a safetensors `checkpoint/`. Local encoder/tokenizer files are fingerprinted. For a remote or cached Hugging Face repository, specify `--revision` with its exact 40-character commit hash; floating `main` revisions are rejected.

```bash
# LoRA reload requires the original local base encoder and saved token limit.
patchlens predict-trained --checkpoint runs/hf-lora/checkpoint --base-model models/encoder --max-length 256 --output runs/lora-reloaded.jsonl

# Add actual predictions, history and representations to a browser report.
patchlens attach-predictions --report examples/fixture-run/report.json --predictions runs/hf-lora/predictions.jsonl --provenance runs/hf-lora/training.json --embeddings runs/hf-lora/embeddings.json --history runs/hf-lora/history.json --run-id lora --name 'LoRA classifier' --output runs/with-lora.json
patchlens export runs/with-lora.json --output runs/lora-workbench
```

The import command chooses the threshold on validation and freezes it for test. It checks dataset fingerprints and exact prediction coverage. If embeddings are omitted, the UI displays “Representations not supplied”; it does not fabricate coordinates from scores.

## Semgrep

```bash
python -m pip install '.[scan]'
patchlens scan --rules integrations/semgrep/review-signals.yml --output runs/semgrep.json
patchlens attach-scan --report examples/fixture-run/report.json --scan runs/semgrep.json --output runs/with-scan.json
patchlens export runs/with-scan.json --output runs/scanner-workbench
```

The included rules are three deliberately limited syntactic review signals, not comprehensive security analysis. The actual reference scan used Semgrep 1.137.0: all 48 input files were listed as scanned, three findings were reported and no scanner errors were returned. Raw findings, rule fingerprint and coverage are in `examples/semgrep/scan.json`. Labels and model scores are unchanged.

## CodeQL and SARIF

Install the CodeQL CLI and JavaScript query packs separately under the terms applicable to your use. The CLI is not bundled. The runner creates a JavaScript database without executing a project build, runs the supplied query suite, and saves stage logs, raw SARIF, manifest and normalized JSON.

```bash
patchlens export-sources --output runs/codeql-input
patchlens scan-codeql --source runs/codeql-input --query-suite codeql/javascript-queries:codeql-suites/javascript-code-scanning.qls --output runs/codeql
patchlens attach-scan --report examples/fixture-run/report.json --scan runs/codeql/scan.json --output runs/with-codeql.json
patchlens export runs/with-codeql.json --output runs/codeql-workbench
```

Alternatively, import a real SARIF 2.1.0 file from a scanner. Its artifact paths must correspond to the exported manifest. For `scan-codeql`, use the manifest inside that command's output directory because CodeQL paths are relative to its `src/` source root.

```bash
patchlens import-sarif --sarif runs/codeql/results.sarif --manifest runs/codeql/manifest.json --output runs/normalized.json
```

The parser resolves inline or indexed locations/rules, decodes file URIs, deduplicates findings and retains unmapped locations. A failed invocation stays failed. SARIF alone does not establish complete per-file coverage. Source fixtures provide limited framework context, so broad production queries may find little even in vulnerable examples.

**Validation boundary:** the SARIF parser and CodeQL command orchestration are covered by local tests. The CodeQL executable itself was not installed or run for this release. No CodeQL findings are claimed.

## Local generation

Use an independently obtained local causal-language-model checkpoint with a tokenizer. Encoder classification and causal generation are separate tracks; the classifier's LoRA adapter cannot be used as a code generator.

```bash
patchlens generate --model models/causal-model --prompts configs/generation-prompts.jsonl --seed 17 --max-new-tokens 256 --temperature 0 --output runs/generation
patchlens scan-codeql --source runs/generation --query-suite codeql/javascript-queries:codeql-suites/javascript-code-scanning.qls --output runs/generation-scan
patchlens generation-summary --generations runs/generation/generations.jsonl --scan runs/generation-scan/scan.json --output runs/generation-density.json
```

Prompts, assumptions, model identity, random seeds, decoding settings and raw completions are recorded. Generated source is saved as text and never executed. It may be invalid JavaScript. Syntax and manual security review remain explicitly unperformed. The density measure uses **nonblank physical lines including comments**, not logical statements; it is a scanner proxy and never a manually adjudicated vulnerability rate. Failed or incomplete scans do not produce a density value.

## Primary references

- [PEFT LoRA API](https://huggingface.co/docs/peft/v0.17.0/en/package_reference/lora)
- [Transformers generation API](https://huggingface.co/docs/transformers/v4.56.2/en/main_classes/text_generation)
- [Semgrep JSON and SARIF fields](https://docs.semgrep.dev/semgrep-appsec-platform/json-and-sarif)
- [CodeQL analysis](https://docs.github.com/en/code-security/tutorials/customize-code-scanning/analyze-code)

These documents describe the external tools. PatchLens release validation is recorded separately in [Reproducibility](REPRODUCIBILITY.md).
