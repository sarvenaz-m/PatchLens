# Security and responsible use

PatchLens is research software, not an application-security certification. The fixture collection intentionally contains vulnerable source text for comparison. Neither the core pipeline nor the workbench executes those snippets.

The default experiment is local. The browser has a restrictive content-security policy and disables network connections. Imports are capped at 20 MiB, checked for schema/score coverage, and rendered with escaping. This is not a sandbox for executing arbitrary code; do not add execution of imported snippets.

Numeric checkpoints use JSON rather than pickle. The optional Hugging Face adapter disables remote custom code and requests safetensors. A model download occurs only with the explicit `--allow-download` option. Review external model provenance and dependencies before enabling it. Semgrep is an independently installed program; only supply rules you have reviewed.

For a suspected issue in PatchLens, use the repository's private vulnerability-reporting feature if the maintainer has enabled it. If it is unavailable, open an issue asking for a private reporting channel without posting exploit details, secrets or third-party vulnerable code. Do not assume this initial repository has an operational response SLA.
