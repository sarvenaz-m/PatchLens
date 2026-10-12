# A five-minute research walkthrough

Open the root `index.html` or the GitHub Pages demo. A fresh session opens the real Java reference experiment. **Dataset** offers that report, all five repository folds and the original authored JavaScript fixtures. Previously selected data and review notes are stored locally.

1. **Public benchmark:** show 62 real corrections, 40 repositories and five held-out folds. The six-model table gives each repository equal weight. Explain the 56.0% CodeBERT macro balanced accuracy alongside 40 misses and 15 false alarms, and its paired comparison interval that includes zero. Scroll to the source/encoder provenance and split ledger.
2. **Overview:** the separate reference test contains six before/after pairs. Its pretrained probe scores 41.7% balanced accuracy. This unfavorable small hold-out is retained rather than replaced by the five-fold result. Identity views are explicitly marked; augmentation robustness is not measured.
3. **Code pairs:** inspect a real before/after Java context and use its correction link. Inputs are patch hunks, not necessarily complete methods. Source CVE association explains the inherited label; it does not establish that every shown line is locally vulnerable.
4. **Dataset:** choose a repository fold, inspect its different held-out examples, then return to the reference. Every original appears in exactly one fold's test partition. Training and validation repositories remain distinct within each fold.
5. **Experiments:** move the threshold slider, inspect changed errors and reset it. Stored benchmark decisions keep their validation-selected threshold. An exploratory test-set choice is not a new held-out result.
6. **Diagnostics and comparison:** contrast the lexical baseline with the frozen probe, inspect misses, reliability bins and pair margins. Pair ordering differs from classifying both siblings correctly. The probe's encoder is frozen; its numeric head is trained only on training data.
7. **Review notebook:** add a source observation and review status, save, reload and export a notes backup. Notes change neither labels nor predictions. Select a point in the **Embedding atlas** with the keyboard; PCA is fitted to training representations.
8. **Authored fixtures:** switch Dataset to the original 48-example report. Its reviewed parameter renames and historical Semgrep findings remain an implementation demonstration. Scanner results do not belong to the public Java corpus.
9. **Provenance:** export the current JSON and trace fingerprints, assumptions and labels to the raw artifacts. The public source and licence hashes can be checked with `python scripts/verify_public_benchmark.py`.

Press **Ctrl+K / ⌘K** to search workspaces, code pairs or CWEs. Review-note persistence and comparisons are described in [Analysis and review](ANALYSIS.md).

## Be ready to explain

- **Why use a pretrained probe?** It tests whether frozen code representations transfer to these correction contexts. A train-only linear head makes the fitting boundary explicit. It is not a fine-tuning comparison.
- **Does CodeBERT outperform the baseline?** Its point estimate is 2.29 percentage points higher, but the paired repository interval is −5.42 to +9.58 points. This corpus does not establish superiority.
- **Why are before/after siblings not contrastive positives?** Their contextual labels differ. Public positive views are identity copies. The authored examples retain separate label-preserving renames.
- **Why aren't repositories mixed?** Shared project conventions and related changes can make a random snippet split optimistic. Repository, shared-CVE and lexical-copy grouping are enforced before fitting. Pretraining overlap remains unknown.
- **What comes next?** Reconstruct complete methods, rerun upstream vulnerability tests, independently review labels and evaluate frozen versus fine-tuned models with chronology-aware partitions.

The Java analysis complements Java/Android experience; controlled Python learning objectives, source audit and uncertainty reporting demonstrate transferable research skills. No confidential employer source or prior employer result is used.
