# Model card · version 2.0.0

**Task:** distinguish before/after contexts of documented public Java security corrections. **Primary study:** five repository-disjoint folds on 62 Vul4J pairs, one training seed. **Additional study:** one fixed reference split across three MLP seeds.

| Model | Representation and fitted objective |
|---|---|
| Token baseline | Train-fitted lexical TF-IDF, numeric logistic head |
| Supervised encoder | Same lexical features, 48-unit tanh MLP, 16-dimensional normalized representation, BCE |
| Contrastive encoder | Same MLP, BCE + 0.3 masked contrastive term |
| Security-weighted encoder | Same contrastive model, positive-class weight 3 |
| CodeBERT frozen probe | Real pretrained CodeBERT, mean-pooled 768-dimensional normalized vector, train-only logistic head |
| Constant 0.5 | No training; control at its validation-selected threshold |

All fitted classifiers use 240 full-batch Adam updates, learning rate 0.012 and L2=0.0001. The public MLP positive views are identity copies, with corrected siblings as opposite-label negatives. The probe has no contrastive term or class weighting. The reference linear heads are zero-initialized and deterministic; repeating them across seeds does not provide independent evidence.

## Actual pretrained encoder

Model: `microsoft/codebert-base`, revision `3b0952feddeffad0063f274080e3c23d75e7eb39`, **124,645,632 parameters**. Weights are real pretrained weights from the official publisher, not a locally initialized test transformer. CPU PyTorch 2.8.0+cpu and Transformers 4.56.2 performed the frozen forward passes. Training affects the separate numeric head only.

Inputs have at most 512 tokens including special tokens. Equal head/tail truncation applies to long contexts. Mean pooling excludes padding and special tokens; row L2 normalization needs no corpus fitting. Dropout is disabled and encoder parameters are frozen. Source file pins, code-input token hashes, counts and execution metadata are retained. Saved embeddings support offline numerical replay.

The approximately 499 MB model download is outside the Git package. Loading uses local pinned files, `local_files_only=True` and `weights_only=True`; remote model code is not requested. Download scripts verify bytes against the released model lock. Classifier checkpoints contain validated numeric JSON parameters. Saved NPZ vectors are opened with `allow_pickle=False` and exact ID/order/fingerprint checks.

## Measured behavior

Five-fold macro balanced accuracy is **56.04% for CodeBERT** versus **53.75% for the token baseline**. The paired difference interval includes zero (−5.42 to +9.58 percentage points). CodeBERT's macro ordering is 73.23%, while macro success on both members of a pair is 12.08%. It misses 40 before contexts and flags 15 after contexts out of 62 each. The small reference hold-out gives CodeBERT 41.67% balanced accuracy.

These numbers describe the declared patch-context study. The outputs are uncalibrated scores. Fold-specific heads and thresholds are stored separately; pooled OOF decisions do not define a single model or common inference threshold. Context loss, literal normalization, truncation, language/API coverage, balanced sampling and possible encoder pretraining overlap constrain use. Independent label review and full-program vulnerability validation remain future work.

## Preserved authored and optional paths

The version-1 authored JavaScript experiment and its four numeric models remain inspectable as historical pipeline evidence. Its corrected labels and rename views rely on fixture assumptions. Small fixture F1 values are not promoted as public-code results.

The optional Hugging Face/PEFT frozen/full/LoRA and causal-generation paths are tested with tiny local randomly initialized transformers. Those implementation tests are distinct from the actual pretrained CodeBERT study, which uses frozen representations only. The report provenance and [Reproducibility](REPRODUCIBILITY.md) distinguish these executions. A real CodeQL run remains pending; JavaScript Semgrep findings belong to the authored corpus.
