# Reproducibility and release validation

## Studio refresh — 2026-09-30

The package remains **1.0.0**. This refresh adds diagnostics, comparison, local review notes and a redesigned interface. It preserves the actual 2026-09-29 reference predictions, checkpoints and Semgrep findings. New analysis outputs were computed from those saved scores; the training results have not been relabelled as new executions.

## Reference execution

Version **1.0.0**, Python **3.12.14**, NumPy **2.3.5**, seed **17**, **240 epochs**. All four reference models were actually trained on the committed fixtures. Full scores, frozen validation thresholds, checkpoints and training-fitted PCA coordinates are retained. The experiment ID derives from dataset/configuration/package version; it is not a source-code signature or a globally unique run identifier.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
python -m pip install --no-deps -e .
OPENBLAS_NUM_THREADS=1 patchlens demo --seed 17 --epochs 240 --output runs/reproduced
patchlens repeat --seeds 17 29 43 --epochs 240 --output runs/repeated
```

The core lock describes the tested Python 3.12 environment. Python 3.10 users should install the compatible bounds from `pyproject.toml` instead. Windows users can activate with `.venv\Scripts\Activate.ps1` and omit the POSIX environment prefix. Reports contain timestamps and timings that will differ; compare predictions and metrics separately with appropriate numeric tolerance.

The three-seed study uses the same test set each time. Its sample standard deviation describes optimization variability, not uncertainty over new repositories. No repeated-seed result is selected as a replacement for the declared seed-17 reference.

## Executed checks

| Check | Result and scope |
|---|---|
| Python suite | 57 tests passed; 4 optional neural tests skipped because their dependencies were unavailable |
| JavaScript suite | 18 tests passed, including Python/JavaScript diagnostic agreement, review validation and CSV escaping |
| Fixture syntax | All 48 originals and 48 renamed views passed Node syntax checks without execution |
| Four CPU objectives | Full 240-epoch runs completed; repeated on seeds 17, 29 and 43 |
| Frozen / full / LoRA training | Executed in the prior reference package on 2026-09-29; unchanged neural implementation, not rerun for this refresh |
| Causal generation | Tiny local GPT-2 execution retained from 2026-09-29; unchanged implementation, not rerun for this refresh |
| Semgrep | Version 1.137.0 scanned all 48 exported examples; 3 findings, no reported errors |
| SARIF and CodeQL orchestration | Parser, source mapping and timeout behavior tested; subprocess orchestration tested with test doubles |
| Browser | Playwright 1.62.1 with Chromium 138.0.7204.0; all nine views, search, threshold reset, model/split changes, keyboard point selection, dark mode, matched report import, review-note persistence, command search, escaped imports and JSON/CSV downloads passed |
| Mobile layout | All nine views checked for horizontal page overflow at 390 × 844; actual screenshots inspected |
| Distribution | Wheel built, installed into an isolated target, CLI audit and packaged web/data presence checked |

Current execution logs are in `docs/evidence/`. `neural-reference-tests.txt` preserves the complete 2026-09-29 suite log that included real neural tests. `validation.json` separates current checks from prior executions and records hashes of the unchanged neural files. UI images in `docs/assets/workbench-*.png` are actual browser captures. `workbench-tour.webm` records actual browser interactions. The banner remains an illustrative brand asset. Formal accessibility certification is not claimed.

## What was not demonstrated

The tiny transformer checks verify implementation and checkpoint plumbing. They are **randomly initialized local models**, not pretrained code models or evidence of useful vulnerability detection. No pretrained-model efficacy study, GPU/MPS experiment, real CodeQL executable run, independent public-data benchmark or third-party label review was performed. The CodeQL runner and import path exist, but no CodeQL findings are included. GitHub workflows are supplied and have not yet run in a published repository. Cross-platform validation beyond this Linux environment remains pending.

## Reproduce optional checks

```bash
python -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install '.[train]'
python -m unittest discover -s tests -v
node --test tests/*.test.cjs
node scripts/check-fixtures.cjs
npm install --no-save --package-lock=false playwright@1.62.1
npx playwright install --with-deps chromium
node scripts/browser-smoke.cjs
node scripts/capture-ui.cjs
node scripts/record-tour.cjs
```

If using an existing browser, `PATCHLENS_CHROMIUM_PATH` can select its executable. The release checks used Chromium 138. PyTorch and PEFT tests are skipped when their optional dependencies are absent; a core-only run must not be described as a neural validation run.

## Regenerate reports and graphics

```bash
patchlens scan --rules integrations/semgrep/review-signals.yml --output runs/semgrep.json
patchlens attach-scan --report examples/fixture-run/report.json --scan runs/semgrep.json --output runs/with-scan.json
patchlens export runs/with-scan.json --output runs/scanned-workbench
```

To update the checked-in single-file demo, first promote the intended validated report to `examples/fixture-run/report.json`, regenerate its `workbench/` with `patchlens export`, then run `python scripts/build_single_file.py`. It recomputes the inline-script CSP hashes. The browser validates structure and coverage; it does not authenticate reports or adjudicate labels.

`python scripts/make_banner.py` regenerates the vector repository banner from the report. `python scripts/make_figures.py` regenerates the static data figure with Matplotlib. Before changing the reference run, check dataset provenance and split hygiene, inspect errors and update the model/data cards. See [Integrations](INTEGRATIONS.md) for model, scanner and generation commands.
