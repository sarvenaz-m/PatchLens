# Optional Semgrep review signals

These three local syntactic rules flag dynamic `eval`, `innerHTML` assignments and `document.write`. They do not model data flow, sanitization, whole-program context or all covered CWE families. A hit is an inspection candidate, not an adjudicated vulnerability. A miss is not proof of safety.

Install Semgrep separately in a suitable environment, then run:

```bash
patchlens scan --rules integrations/semgrep/review-signals.yml --output runs/static-review.json
```

The adapter disables telemetry and version checks for the scan command, uses the supplied local configuration and writes temporary source files for the scanner. It does not execute the source. The raw status distinguishes a completed scan from a scan containing errors. Findings remain a separate file; they are not silently merged into model predictions or dataset labels.

The version 0.2 reference scan actually ran Semgrep 1.137.0 on all 48 authored source files, reporting three findings and no scanner errors. See `examples/semgrep/scan.json` for the findings and coverage. Use `patchlens attach-scan` to include a matching scan in a workbench report. Follow [Semgrep's official documentation](https://semgrep.dev/docs/) for installation and rule validation in your environment.
