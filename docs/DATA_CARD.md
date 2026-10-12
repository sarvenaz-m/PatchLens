# Data card · version 2.0.0

## Public corpus

**Name:** Vul4J public Java patch contexts. **Size:** 62 corrections, 124 before/after originals, 40 source repositories, 40 split components. **Categories:** 22 upstream CWE numbers plus `CWE-unknown`. Nine pairs lack a mapped CWE; their 18 contexts keep that explicit value rather than receiving an invented category.

**Source:** [Vul4J](https://github.com/tuhh-softsec/Vul4J), revision `376411da11fa705019f731404de1d0679fe73537`, original entries 1–79 of the committed dataset CSV. Bui, Scandariato and Díaz Ferreyra, MSR 2022, [DOI](https://doi.org/10.1145/3524842.3528482). Dataset metadata is CC-BY-4.0. Original code excerpts and patches retain their upstream terms; retained licence texts and notices are in `datasets/vul4j/licences/` and [Third-party notices](../THIRD_PARTY_NOTICES.md).

A sample is concatenated production Java Git diff hunk context for one documented security correction. `label=1` is the before context and `label=0` the after context, specific to its CVE and original surrounding program. These labels were inherited, not independently adjudicated for the extracted snippets. No source code, build command, patch or vulnerability test is executed by the importer. Other vulnerabilities can remain in an after version.

Tests and examples are removed from classifier input using documented path heuristics. Empty/unchanged contexts, missing CVEs, multi-commit renderings, inaccessible sources and insufficient licence retrieval are explicit eligibility exclusions. The complete source lock and 17-entry exclusion ledger are committed. Eligibility does not depend on model performance. Raw patch files retain their original content, including upstream authorship and changed tests.

The reference split contains 47 / 9 / 6 pairs across 28 / 6 / 6 repositories. Five additional repository folds test every pair once, fitting vocabulary/heads and selecting thresholds independently within each fold. Shared-CVE and code-copy grouping precedes assignment. The cohort is a small permissive/retrievable subset, balanced by construction, with several corrections per repository. It is not representative of deployed vulnerability prevalence.

`view_code` is identical to `code` for all public samples. View scores are the same inference input; rename or augmentation stability is not measured. Patch-hunk extraction can omit definitions, callers and control/data flow. CodeBERT truncates 32 contexts using a fixed head/tail rule. Exact lexical checks and 5gram overlap do not establish semantic independence, and pretraining overlap remains unknown.

## Authored corpus, preserved from version 1

`src/patchlens/data/fixtures.jsonl` contains 24 authored JavaScript vulnerable/corrected pairs, 48 originals, across six CWE categories. Source markers begin with `authored:` and the fixtures are CC0-1.0. A documented local parameter rename supplies their label-preserving view. Scenario groups keep siblings together, using 24/12/12 originals in train/validation/test.

These examples support numerical, syntax and pipeline checks. Their stylistic consistency and small test set limit model-quality claims. The original reference report, four numeric models, three-seed study and Semgrep findings remain labelled as that corpus's prior executions. They are separate from the public Java reports.

## Contract and provenance

Both corpora use the existing strict Example schema: IDs, pair/group/split, binary label, CWE, title, original/view code, rationale, assumptions, source, licence and review status. Pairs have one member of each class and share split/group/CWE. The audit rejects duplicate IDs, cross-split groups, contradictory identical code and whitespace-normalized code leakage.

Public provenance adds a companion cohort ledger: original CVE/repository, correction URL, raw patch SHA-256, extracted files/hunk windows, before/after code hashes, upstream failing-test names, licence source/revision and exclusion reason. Dataset fingerprints cover actual code, labels and split assignments. Fold fingerprints change when split metadata changes; original input codes and frozen vectors are verified to remain identical.

Reports do not authenticate the provider or establish independent ground truth. Pins make the released bytes reproducible. Model/scanner findings never rewrite labels. Contribution guidance is in [CONTRIBUTING.md](../CONTRIBUTING.md).
