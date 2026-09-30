# Contributing

Useful contributions include independently reviewed labels, stronger split audits, additional label-preserving views, carefully scoped static-analysis rules and reproducible model adapters.

1. Explain the research or inspection problem in an issue.
2. Keep changes scoped; include data provenance, licence and assumptions for new examples.
3. Run the Python tests, Node tests and fixture syntax check in the README.
4. For UI changes, run the browser smoke suite and inspect desktop, mobile and dark appearance.
5. For numerical changes, include a discriminating test, retain raw predictions and explain any change to reference results.

Never include proprietary snippets, customer data, credentials or third-party code without adequate reuse rights. Do not turn scanner outputs into ground-truth labels without independent review. Keep vulnerability-fix lineages and derived examples in the same split.

State which optional integrations you actually ran. A proposed experiment or untested adapter must not appear as a completed benchmark.
