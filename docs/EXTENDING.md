# Extension guide

## Add a dataset

Use the exact JSONL schema in the data card. Keep security-changing siblings and all derived views in one group and split. For repository-derived code, group at least by repository/patch lineage and perform additional clone checks; arbitrary IDs cannot enforce that semantic grouping. Record licence and a traceable source for each sample. Use independent review to adjudicate context, vulnerability mechanism and patch adequacy.

```bash
patchlens audit my-data.jsonl
patchlens demo --dataset my-data.jsonl --output runs/my-data
```

The audit accepts up to 10,000 examples, 50,000 characters per code field and 20 MiB per input file. The deliberately full-batch CPU training backend allows at most 512 training originals. Larger studies need a minibatch backend and a suitable negative-sampling protocol.

## Import external predictions

Each prediction line must contain `id` and a numeric `score` in [0,1]; `view_score` is optional for CLI evaluation. IDs must cover the entire dataset exactly, without duplicates or extras. The positive class is always vulnerable. The workbench report format requires both original and view scores plus full run/provenance fields; a raw predictions file is not itself a workbench report.

`patchlens evaluate` evaluates an explicitly supplied threshold. It does not tune it. Select thresholds on validation separately and carry the exact float into test evaluation.

## Hugging Face classifier adapter

```bash
python -m pip install '.[hf]'
patchlens predict-hf --model /path/to/local-binary-checkpoint --vulnerable-class 1 --output runs/hf-scores.jsonl
```

The checkpoint must already be fine-tuned for binary sequence classification. A base encoder with a newly initialized head is rejected. Use safetensors and a tokenizer recognized by installed Transformers. Remote custom model code is disabled. The default is local-only; `--allow-download` enables model fetching, and `--revision` can pin a repository commit. Record the checkpoint's training data and compare it for overlap with your evaluation set. The adapter runs on CPU and truncates to 512 tokens, so examine truncation before interpreting large snippets. The local checkpoint path is exercised by the tiny-transformer tests; downloaded pretrained checkpoint quality remains unvalidated.

## A concrete next LLM experiment

1. Assemble licensed, independently reviewed public JavaScript patches, with repository-level splits and clone audits.
2. Freeze a documented pretrained encoder checkpoint and tokenizer; measure a frozen-encoder classifier baseline.
3. Compare supervised fine-tuning, paired contrastive fine-tuning and an added positive-class weighting term. Use LoRA only on supported target modules and record trainable parameter counts.
4. Review label-preserving transformations and the treatment of false negatives in the contrastive candidate set.
5. Tune only on validation, repeat seeds, publish raw predictions and analyze grouped uncertainty.
6. Run versioned static rules independently, then adjudicate model/scanner disagreements.

The public-data study remains proposed. The optional training, LoRA, CodeQL orchestration and generation implementations are now available; see [Integrations](INTEGRATIONS.md) for exact commands and what was actually executed.

## Workbench integration contract

The report includes `schema_version`, `project`, `experiment_id`, `dataset`, `environment`, `config`, `samples`, `runs`, `static_analysis` and `limitations`. A run holds all predictions, its validation operating point, per-split metrics, objective history and training-fitted PCA points. Use `examples/fixture-run/report.json` as a concrete reference. The browser checks structure, finite scores and exact sample coverage. Hashes are provenance records, not cryptographic signatures or authentication.

Preserve escaped rendering and CSP when extending the interface. Do not execute snippets, add implicit network traffic or reclassify scanner silence as ground truth.
