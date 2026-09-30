# Dataset card · authored-fixtures-v1

| Property | Value |
|---|---|
| Origin | Newly authored educational JavaScript examples |
| Size | 48 examples / 24 vulnerable–corrected pairs / 24 scenario groups |
| Split | 24 training, 12 validation, 12 test examples |
| Classes | Balanced within each split; vulnerable is positive |
| Views | One local-parameter rename per example |
| Sources | `authored:patchlens-fixtures-v1` |
| Licence | CC0-1.0 dedication for the fixture dataset |
| Label review | Author-labelled; independent review pending |
| Intended use | Pipeline verification, method illustration and error inspection |
| Excluded claims | Representative prevalence, production accuracy, exploit validation |

## Coverage

| CWE | Scenarios | Correction mechanisms and assumptions |
|---|---:|---|
| CWE-79 · cross-site scripting | 4 pairs | Text-node APIs for text content; appropriate DOM context |
| CWE-89 · SQL injection | 4 pairs | Parameter binding or explicit sort-direction allowlist; PostgreSQL-style API assumptions |
| CWE-78 · OS command injection | 4 pairs | Argument-array process APIs, option delimiters or constrained inputs; named utility behavior |
| CWE-22 · path traversal | 4 pairs | Canonical containment or fixed allowlists; filesystem/symlink/TOCTOU assumptions stated per example |
| CWE-1321 · prototype pollution | 4 pairs | Fixed property paths, own-property allowlists or null-prototype dictionary boundaries |
| CWE-95 · dynamic-code evaluation | 4 pairs | Data parsing or explicit operation dispatch replacing attacker-controlled evaluation |

For each category, the first two authored scenarios train the model, the third is validation and the fourth is test. This split is deliberate and inspectable, not a randomized population sample. The same authoring style and related APIs cross splits. Groups prevent scenario leakage but do not establish repository-level independence.

## Schema

Each UTF-8 JSONL line contains exactly these keys:

| Key | Meaning |
|---|---|
| `id` | Unique example identifier; safe alphanumeric/dot/hyphen/underscore string |
| `pair_id`, `group_id` | Pair and split-group identity |
| `split` | `train`, `validation` or `test` |
| `label` | Integer 1 for vulnerable; 0 for corrected in context |
| `cwe`, `title` | Weakness family and scenario title |
| `code`, `view_code` | Original source and reviewed label-preserving view |
| `rationale`, `assumptions` | Why the label applies and when the correction is valid |
| `source`, `licence` | Traceable origin and reuse terms |
| `review_status` | Explicit label-review status |

The generator is `scripts/build_fixtures.py`; the source of truth for a run is the audited JSONL file and its SHA-256. Code strings are never executed by the pipeline or browser. `scripts/check-fixtures.cjs` checks JavaScript syntax without running the snippets. Syntax checks do not verify security semantics or API behavior.

## Restrictions and known weaknesses

The examples are short and lack real repository history, dependencies, tests, complex control flow and business logic. Corrections cover a specific weakness; authorization, resource limits and other concerns may be outside scope. Some filesystem corrections depend on a trusted, stable directory tree. Scanner silence must not upgrade a contextual label into a safety guarantee.

No employer repositories, confidential snippets, private datasets or personal records were used. Do not add such material. Add third-party patches only after reviewing licence, provenance, confidentiality, split lineage and label evidence.

## Dataset dedication

To the extent permitted by law, the fixture author dedicates these newly authored dataset records to the public domain under [CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/). The full licence text is linked there. Code and documentation outside the fixture dataset are under the repository MIT licence unless otherwise noted.
