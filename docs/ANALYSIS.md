# Diagnostics, comparison and review

The studio analyzes recorded scores. Opening these views does not retrain a model or change a dataset label. The selected evaluation split applies across the workspace; model comparison uses its own two selectors and each model's stored validation threshold.

## Public-study aggregation

Version 2.0.0 adds a separate Public benchmark workspace. It pools fold-specific classification decisions, then gives each repository component equal weight for macro balanced accuracy, pair ordering and complete-pair success. The 2,000-draw intervals resample whole components; overlapping fold training sets limit inference. Raw scores from different folds are not pooled into a common ROC/AUC or threshold. Per-report diagnostics below operate on the currently selected split. The historical six-group examples in the CLI walkthrough refer to the authored fixture report.

## Diagnostics

| Measure | Meaning | Important limit |
|---|---|---|
| Balanced accuracy | Mean of vulnerable recall and corrected-example specificity | Undefined when a class is absent |
| Matthews correlation | Confusion-matrix correlation, from −1 to +1 | Displayed as unavailable when its denominator is zero |
| Brier score | Mean of `(score − label)²` | Lower is better; scores remain uncalibrated outputs |
| Log loss | Mean negative binary log likelihood | Scores are clipped to `[1e−15, 1−1e−15]` for logarithms only |
| Expected calibration error | Count-weighted absolute difference between mean score and observed positive fraction | Ten equal-width bins; sensitive to bin choice and sample size |
| Pair margin | Vulnerable score minus its corrected sibling's score | A positive margin does not imply both classifications are correct |

The reliability diagram places each occupied bin at its mean score and observed vulnerable fraction. The vertical segment is a 95% Wilson interval for that fraction. Empty bins are retained in JSON and omitted from the plot. A score of exactly 1 belongs to the last bin. Intervals on authored, dependent examples are descriptive and do not establish population coverage.

Weakness slices retain their own class counts. Their miss-rate intervals use the vulnerable-example denominator. Selecting a CWE opens the corresponding code pairs in the current split. The pair-margin list is ordered from smallest to largest so reversed or tied ordering appears first.

```bash
patchlens analyze examples/fixture-run/report.json \
  --run weighted --split test --bins 10 --output runs/diagnostics.json
```

The command independently audits examples and checks the declared dataset SHA-256 against the actual sorted source records. It joins scores by exact ID, rejects missing/duplicate scores, and verifies agreement between the saved threshold and its provenance.

## Paired comparison

Choose two models from the current report, or import a second report. Comparison requires the same IDs, original and renamed code, contextual labels, category, group, split and descriptive source fields. A matching asserted hash alone is insufficient. Prediction order may differ.

Each example is classified as improved, regressed, correct in both, or wrong in both. The UI highlights changed decisions and shared errors; the CSV includes every example in the selected split. Formula-like text fields are escaped for spreadsheet import. The exploratory threshold slider does not alter this comparison.

```bash
patchlens compare examples/fixture-run/report.json \
  examples/repeated-study/seed-29/report.json \
  --baseline-run weighted --candidate-run weighted --split test \
  --draws 1000 --seed 17 --output runs/seed-comparison.json
```

The CLI adds a paired group bootstrap for the candidate-minus-baseline accuracy difference. For each draw, it samples `group_id` values with replacement, includes every member of every sampled group, and applies the same sampled groups to both models. The percentile interval uses the 2.5th and 97.5th percentiles. Draws are bounded to 200–2,000 and computed in batches. Fixed seeds reproduce results in the recorded NumPy environment.

Only six groups occur in the bundled test split. The resulting interval is exploratory; it is not evidence of general superiority or a guarantee on new repositories. Thresholds remain fixed throughout resampling. No threshold is selected using test outcomes.

## Review notebook

Review states are **Not reviewed**, **Needs attention** and **Reviewed**. These record workflow progress and do not certify security, change the fixture's independent-review status or revise ground-truth labels.

1. Choose the evaluation split and an example.
2. Inspect the source and stated assumptions; open its pair for comparison.
3. Enter a note and select a review status, then choose **Save review**. Unsaved drafts survive navigation within the current session; reloads require a saved entry.
4. Use **Export notes** to keep a portable backup.

Saved entries are scoped to the dataset fingerprint in browser local storage, with at most 5,000 characters per note. If browser storage is unavailable, the interface reports that the entry is kept only for the current session. Browser privacy settings, moving the HTML file, changing browser profiles or clearing site data can affect persistence. Keep exported backups for durable work.

Import accepts only matching dataset fingerprints, known unique sample IDs, valid statuses and timestamps. It merges newer entries by timestamp; entries with equal or older timestamps do not replace existing notes. Notes are rendered as text. **Export JSON** in the main toolbar continues to export the original experiment report; it does not include review notes or exploratory slider changes.

## Keyboard navigation

**Ctrl+K / ⌘K** opens workspace search. Type a page name, code-pair title or CWE, then use the arrow keys and Enter. Escape closes the dialog. Selecting a code pair from search also selects its correct split. Standard Tab navigation reaches controls and embedding points; Enter or Space opens a focused point.

## Implementation map

| File | Responsibility |
|---|---|
| `src/patchlens/analysis.py` | Source audit, diagnostics and paired group bootstrap |
| `src/patchlens/web/analysis.js` | Pure metrics, matching, review validation and CSV encoding |
| `src/patchlens/web/workspace.js` | Diagnostics, comparison, review storage and command search |
| `src/patchlens/web/studio.css` | Studio layout, component styles and responsive behavior |
| `tests/test_analysis.py` | Numerical cases, provenance checks and group resampling behavior |
| `tests/analysis.test.cjs` | Independent Python/JavaScript agreement and import/export contracts |

The original schema 1.0 report and all prior CLI commands remain supported. The package version is **2.0.0**; schema 1.0 compatibility is retained.
