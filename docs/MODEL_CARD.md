# Model card · CPU reference baselines

**Version:** 1.0.0 · **Task:** binary vulnerability classification under fixture assumptions.

Four independently fitted models are supplied as numeric JSON weights. One is logistic regression over lexical TF-IDF features; three use a small MLP encoder with supervised, contrastive or security-weighted contrastive training. None is a pretrained LLM, a generative model, a static analyzer or a verified remediation system.

Training data consists of 24 authored originals and 24 derived renamed views. Validation and test each contain 12 authored originals plus their derived views for stability analysis. All checkpoints were fit by the included code. No third-party model weights are bundled.

Intended users are researchers and engineers evaluating pipeline design and inspecting classification behavior. Expected outputs are uncalibrated vulnerability scores and representations. A score near zero must not be interpreted as evidence that a program is secure. Unknown APIs, larger snippets, alternate syntax and different distributions can produce arbitrary failures.

Reported fixture results and detailed settings are in the README and `examples/fixture-run/report.json`. The security-weighted variant does not outperform the ordinary contrastive variant in the included test run. The primary report uses seed 17. A separate three-seed study is included; six test positives and repeated optimization on the same split still do not support a robust comparative claim.

`patchlens predict` loads JSON numeric parameters with shape and finite-value checks. Hugging Face checkpoints use a separate optional adapter, must already contain a complete binary classifier, and require an explicit vulnerable-class index. Those external models are outside this model card and were not exercised in the reference run.

The next evaluation should use independently reviewed, licensed public data, repository-disjoint splits, repeated seeds, calibrated scores where appropriate and adjudicated model/scanner disagreements. See `METHODOLOGY.md` and `DATA_CARD.md` before interpreting results.

## Optional neural path

This card describes the four bundled NumPy reference models. The optional Hugging Face/PEFT implementation was tested with tiny randomly initialized local transformers; those tests do not create a pretrained security model or support a model-quality claim. See INTEGRATIONS.md for training, checkpoint provenance and inference.
