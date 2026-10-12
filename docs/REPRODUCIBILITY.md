# Reproduce PatchLens 2.0.0

Release date: **2026-10-04**. The public CPU experiments, source reconstruction, checkpoint replay and actual browser checks were executed in this release workflow. Version-1 fixture checkpoints and scanner findings remain separately attributed to their original executions.

## What is included

The repository contains 62 attributed Vul4J patch pairs, 124 extracted production Java contexts, the fixed 40-component split ledger, original patch/licence bytes, CodeBERT embedding arrays, six classifier checkpoints per run, raw predictions, three reference seeds and all five repository folds. The approximately 499 MB encoder weights are downloaded separately and ignored under `.cache/`.

The tested environment used Python 3.12.14, NumPy 2.3.5, PyTorch 2.8.0+cpu, Transformers 4.56.2, safetensors 0.6.2 and four CPU inference threads. PEFT 0.17.1 was installed for the optional tiny-model integration tests. `requirements-benchmark-lock.txt` and `requirements-neural-lock.txt` record those environments. For other Python versions/platforms, use the supported bounds in `pyproject.toml`; a Python-3.12 CPU lock is not a cross-platform lock.

## Verify existing artifacts without downloads

Run from the repository root:

```bash
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements-lock.txt
python -m pip install --no-deps -e .
python scripts/verify_public_benchmark.py
python -m unittest discover -s tests -v
node --test tests/*.test.cjs
node scripts/check-fixtures.cjs
```

The replay reconstructs retained snippets from raw patch bytes, verifies hashes and fold assignment, reloads numeric classifiers, reselects validation thresholds and recomputes example/pair/repository metrics and the OOF summary. It checks **5,952 original/view predictions** and **144 split metric/macro states**. This verifies the supplied numerical artifacts; it does not perform a new encoder forward pass or run the upstream vulnerability tests.

Tests for the optional transformer adapters skip if their dependencies are absent. The release's **75-test Python run installed these dependencies and had no skips**. A core-only run must retain its actual skip count.

## Refit classifiers from saved representations

```bash
patchlens benchmark --embedding-cache examples/public-benchmark/encoder --output runs/public-replay
patchlens cross-validate --embedding-cache examples/public-benchmark/encoder --output runs/five-fold-replay
```

These commands fit all numerical heads anew, including vocabulary and IDF on each training partition only. Saved label-independent CodeBERT vectors are reused after order, dataset and byte-fingerprint checks. The public corpus has identity views; it does not test rename invariance. Three reference seeds share one split; the five-fold study uses seed 17.

## Reconstruct the public corpus

```bash
python scripts/fetch_public_sources.py data --output .cache/vul4j
patchlens prepare-public --cache .cache/vul4j \
  --lock datasets/vul4j/source-lock.json --output runs/imported-vul4j
```

Downloads verify the release's source-byte pins and execute no upstream code. The source lock records unavailable/non-selected candidates as well as successful downloads. See [Public benchmark](PUBLIC_BENCHMARK.md) for selection rules and [Data card](DATA_CARD.md) for label scope. Existing source/licence files also allow offline verification without relying on continued upstream availability.

## Run a fresh pretrained CPU inference

```bash
python -m pip install -r requirements-benchmark-lock.txt
python -m pip install --no-deps -e .
python scripts/fetch_public_sources.py model --output .cache/codebert-base
patchlens benchmark --model-dir .cache/codebert-base --output runs/fresh-public
patchlens cross-validate --embedding-cache runs/fresh-public/encoder --output runs/fresh-five-fold
```

The encoder is `microsoft/codebert-base` at revision `3b0952feddeffad0063f274080e3c23d75e7eb39`; tokenizer and weight hashes are in `configs/codebert-lock.json`. Loading is local-only, disables remote custom code and uses PyTorch's restricted weight loader. The encoder stays frozen in evaluation mode. The output is mean pooling over non-special/non-padding tokens followed by row L2 normalization. The fixed 512-token budget uses equal head/tail truncation, including two special tokens. A train-only linear head uses the declared full-batch Adam protocol.

Actual release inference processed **124 contexts in 40.72 seconds** on this CPU environment; timings vary by host. It recorded **32 truncations** and no pair with identical visible tokens after truncation. Preserve these diagnostics in a fresh run. This is a frozen representation comparison, not fine-tuning or a causal ablation of pretraining.

JSON timestamps, elapsed times and experiment IDs can differ on a fresh run. Compare source fingerprints, protocol, predictions and metrics with numerical tolerance, rather than asserting byte-identical reports. CodeBERT's zero-initialized probe is deterministic; repeated seeds yield identical predictions in this environment.

## Executed validation

| Check | Release result |
|---|---|
| Python | 75 passed; no skips, including genuine tiny BERT/GPT-2 and PEFT adapter executions |
| JavaScript | 23 passed; includes independent agreement on 144 Python/JS metric states and hostile metadata/import cases |
| Source/record replay | 62 raw patches reconstructed, 40 repositories separated, all retained source/licence hashes checked |
| Numerical replay | 5,952 checkpoint predictions, validation thresholds, 144 metric/macro states, 124 OOF originals per model |
| Pretrained encoder | Actual pinned CodeBERT CPU forward pass on all 124 originals |
| Model fitting | Six models, reference seeds 17/29/43, plus five separate repository folds at seed 17 |
| Authored fixture syntax | All 48 originals and 48 renamed views checked without executing snippets |
| Browser | Playwright 1.62.1; actual Chrome 154.0.8037.92, ten public-study views, seven corpora, every fold, source links, imports and exports |
| Mobile | Ten views at 390 × 844; no horizontal page overflow; actual light/dark captures |
| Offline behavior | No external HTTP request or page error during public browser checks |
| Distribution | Wheel installed into an isolated target; CLI, fixtures and packaged web resources checked |

Detailed current logs and counts are in `docs/evidence/*-v2.*` and `validation-v2.json`. Older files without the `-v2` suffix preserve historical version-1 evidence; they are not new v2 execution logs.

## Browser, figures and the single-file demo

```bash
npm install --no-save --package-lock=false playwright@1.62.1
npx playwright install --with-deps chromium ffmpeg
node scripts/browser-public.cjs
node scripts/browser-smoke.cjs
node scripts/capture-ui.cjs
node scripts/record-tour.cjs
python scripts/make_preview.py
```

Set `PATCHLENS_CHROMIUM_PATH` to use an existing executable. In a container requiring it, `PATCHLENS_NO_SANDBOX=1` selects the relevant Chromium launch flag; this is not needed for ordinary local use. FFmpeg on the system PATH is required to convert the actual video to GIF.

```bash
python -m pip install matplotlib==3.10.8
python scripts/make_banner.py
python scripts/make_public_figures.py
python scripts/build_single_file.py
```

The builder uses `examples/public-benchmark/report.json`, adds the authored report and all five folds, escapes embedded JSON and recomputes CSP script hashes. `--report` and `--output` can select an alternate main report/output. To update separately exported workbenches, use `patchlens export REPORT --output DESTINATION`. Figures and the banner read actual checked-in summary values; captures require the rebuilt demo.

## Preserved integrations and remaining work

The original authored four-model/three-seed experiment and Semgrep 1.137.0 findings remain in their version-1 directories. Semgrep was not re-run on the public Java corpus. The current optional neural tests execute small, randomly initialized local models to verify adapter behavior; they do not establish pretrained efficacy. The separate real pretrained comparison is the frozen CodeBERT study above.

No upstream Vul4J PoV execution, independent local-label adjudication, real CodeQL executable run, GPU/MPS benchmark or cross-platform execution was added. GitHub workflow files are supplied; their remote runs have not been observed in this preparation. The study's repository intervals are exploratory and cannot rule out overlap with encoder pretraining. See [Public benchmark](PUBLIC_BENCHMARK.md) and [Integrations](INTEGRATIONS.md).
