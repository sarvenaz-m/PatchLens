# A five-minute research walkthrough

Open the root `index.html`. It includes genuine fixture predictions and the Semgrep review scan, with no server or API key.

1. **Overview:** explain the positive class and show the raw confusion counts. The reference test set has only six vulnerable and six corrected examples. One miss changes recall by 16.7 percentage points.
2. **Code pairs:** select “Updating a configuration branch.” The reference security-weighted model misses this authored prototype-pollution example. Explain the stated assumptions before describing the correction.
3. **Experiments:** move the threshold slider and observe the changed errors. Reset it. The stored comparison still uses validation-selected thresholds; exploratory test-set choices must not be reported as a new held-out result.
4. **Diagnostics:** inspect the reliability diagram, uncertainty in each CWE slice and whether a correction reduces the model score.
5. **Model comparison:** compare the token baseline with the weighted encoder; one test decision improves while one shared error remains. Import a matched seed report for another comparison.
6. **Review notebook:** write an observation, save its status, reload the page and export a notes backup. Notes never change labels or the original report.
7. **Embedding atlas:** select a point using the keyboard and open its pair. PCA is fitted on training representations; a visually separated plot is not evidence of reliable generalization.
8. **Tool findings:** inspect the independent syntactic scanner signal. The limited Semgrep rules cover only a few sinks. Inspect a disagreement rather than treating either source as a security verdict.
9. **Provenance:** inspect the dataset fingerprint, source, assumptions and review status. Export the JSON; the same raw scores underlie the charts.

Press **Ctrl+K / ⌘K** to jump to a workspace or find a code pair. The complete analysis and notebook behavior is documented in [Analysis and review](ANALYSIS.md).

## Questions worth being ready to answer

**Why isn't the correction the positive contrastive view?** It changes the relevant security label. The reviewed rename is the positive; the opposite-label sibling is a useful hard negative.

**What does positive-class weighting establish?** It changes the differentiable training objective. Whether it improves the FNR/FPR trade-off requires held-out evaluation; the fixtures cannot establish a general effect.

**What changed across seeds?** Seeds 17, 29 and 43 share the same split. The weighted model catches one additional vulnerable example at seed 29 but also raises one false alarm. This is descriptive optimization variation on the same small test set, not three independent benchmarks.

**Was LoRA actually tested?** Yes: an actual PEFT adapter was optimized on a small locally initialized BERT classifier, saved, reloaded and checked against the original predictions. This verifies implementation. It does not demonstrate fine-tuning effectiveness on a pretrained code model.

**What would a credible next experiment require?** Independently reviewed public patches with suitable licences, repository/lineage-disjoint partitions, clone audits, controlled pretrained-model comparisons and uncertainty estimates that respect data dependence.

Run and understand the code before presenting it. No confidential employer code, private dataset or previous employer result is included.
