# Public Java study · version 2.0.0

PatchLens evaluates whether a classifier can distinguish the context before a documented security correction from the context after it. The source is [Vul4J](https://github.com/tuhh-softsec/Vul4J), pinned at `376411da11fa705019f731404de1d0679fe73537`. The inputs are patch-centred Java excerpts, not complete compilable functions or programs. Labels inherit the upstream vulnerability/patch association; no local PoV was rerun.

## Corpus construction

The eligibility pool is the original PoV-based entries **VUL4J-1 through VUL4J-79**. The later SpotBugs-only entries are outside this protocol. A pair needs a retrievable patch, a CVE identifier, an explicit retained permissive upstream licence and changed nonempty production Java contexts. Git diff hunks are parsed with both old and new line counts checked. Tests/examples are excluded from model inputs, while raw upstream patch files remain intact for provenance. File names, offsets, repository names, CVE metadata and before/after markers are not added to classifier input. Existing code comments remain available to CodeBERT; the lexical tokenizer drops them.

Selection happens before fitting. All 62 eligible pairs are retained, including errors, long contexts and a pair whose literal change disappears under lexical normalization. The exclusion ledger covers all 17 other source entries:

| Reason | Entries |
|---|---:|
| Missing CVE identifier | 3 |
| Original patch URL unavailable | 1 |
| Multi-commit patch rendering | 3 |
| Upstream licence not retrieved at the selected source point | 10 |

`datasets/vul4j/source-lock.json` pins downloaded bytes. These are release-computed hashes, not checksums supplied by the data provider. GitHub can render a merge commit's `.patch` through its constituent commit; the released patch bytes and the original Vul4J link are both preserved. This importer does not reconstruct or claim a complete parent/fixed repository checkout.

## Split and fitting rules

Repository components join shared CVEs, identical comment/spacing-free lexical contexts, or token-5gram Jaccard overlap of at least 0.90, requiring at least 25 unique grams. Exact canonical label conflicts are excluded rather than silently adjudicated. The heuristic does not prove semantic clone independence.

Components are ranked by a seed-17 SHA-256 rule, independently of scores and model performance. The reference split assigns 28 components to train, six to validation and six to test: **94 / 18 / 12 contexts**. Three training seeds, 17/29/43, vary MLP initialization on that fixed split.

The five-fold study assigns each component's position in the same fixed ledger modulo five. Fold `f` tests bucket `f`, validates on `(f+1)%5`, and trains on the remaining three. Each fold has **24 / 8 / 8 components**; example counts differ because repositories contribute different numbers of patches. Each of the 124 originals contributes exactly one held-out decision per model. One declared training seed, 17, is used for this study.

A fresh lexical vocabulary/IDF and classifier are fitted within each training split. CodeBERT is frozen and applies a row-wise representation transform without fitting to this corpus; every fold refits its linear head using training labels only. Thresholds maximize validation recall under an FPR ceiling of 0.20 and are frozen before test. A validation ceiling does not guarantee that rate on test.

## Pretrained representation

[microsoft/codebert-base](https://huggingface.co/microsoft/codebert-base), revision `3b0952feddeffad0063f274080e3c23d75e7eb39`, has 124,645,632 parameters. The CPU execution used PyTorch 2.8.0+cpu and Transformers 4.56.2. All weight and tokenizer file hashes are in `configs/codebert-lock.json`.

At most 510 code tokens plus two special tokens enter the model. Longer inputs keep equal head/tail halves using a fixed rule. **32 contexts** are truncated; **zero pairs** become identical in the retained token stream. Mean pooling excludes padding and special tokens, followed by row L2 normalization. The numeric logistic head trains for 240 Adam updates at learning rate 0.012 with L2=0.0001. No transformer weights are fine-tuned.

The lexical/MLP comparison keeps the version-1 feature extraction and hyperparameters. Public-code `view_code` is the original itself: contrastive positives are identity copies. That condition is explicit, and no augmentation robustness is inferred. Literal normalization makes VUL4J-26 lexically identical across the two versions; that failure case remains counted.

CodeBERT and the lexical baseline also differ in input treatment and representation size. The experiment compares practical methods; it does not isolate pretraining as a causal factor. CodeBERT's possible exposure to these projects or corrections during pretraining cannot be ruled out.

## Metrics and interpretation

All three reported percentage measures are **macro averages over repository components**. Balanced accuracy gives equal weight to both classes. Pair ordering requires the before score to exceed its sibling's after score. Complete-pair success requires both predictions to be correct at that fold's threshold. Confusion/error counts pool the 124 individual decisions.

Five-fold macro balanced accuracy: token baseline **53.75%**, CodeBERT **56.04%**. The paired repository difference is **+2.29 points**, with an exploratory 95% interval of **−5.42 to +9.58 points**. CodeBERT has **73.23% macro pair ordering** but only **12.08% macro complete-pair success**. It misses 40 of 62 before contexts and raises 15 alarms among 62 after contexts. These outcomes do not establish broad detection efficacy or comparative superiority.

The reference hold-out independently remains visible: CodeBERT balanced accuracy **41.67%**, token baseline **50.00%**, over six pairs. No favourable split or seed replaces it.

Bootstrap intervals draw whole repository components, 2,000 times, using seed 17. The OOF paired comparison uses the same drawn components for both models. Training sets overlap across folds; small corpus size, contextual labels and selection limit interpretation. Fold-specific binary decisions are pooled. Raw scores from different fitted heads are not combined into a common ROC/AUC or one deployment threshold. Per-CWE Wilson bands in the inspection UI are descriptive and do not account for repository dependence.

## Inspect and reproduce

- `examples/public-benchmark/`: reference seeds, saved encoder vectors, numeric checkpoints and reports.
- `examples/repository-cross-validation/fold-0` through `fold-4`: actual fold inputs, splits, reports and checkpoints.
- `oof-predictions-*.jsonl`: one held-out decision per original, including fold, score and its actual validation threshold.
- `cross-validation-summary.json`: all metrics and paired repository uncertainty.
- `python scripts/verify_public_benchmark.py`: source reconstruction, classifier replay and threshold/metric verification without downloading the encoder.

The public demo bundles the reference report and all five fold reports. Use its Dataset selector to inspect the code behind any fold's errors. See [Reproducibility](REPRODUCIBILITY.md) for fresh source and encoder downloads.
