# Methodology

## Version 2 public study

The public study follows [PUBLIC_BENCHMARK.md](PUBLIC_BENCHMARK.md): 62 real Java patch pairs, repository components, a frozen CodeBERT probe, a fixed reference split and five outer folds. All three percentage measures in the public results are repository macro averages. Whole components provide exploratory bootstrap intervals; OOF decisions use each fold's own validation threshold. No cross-fold score AUC is claimed.

The equations below describe the unchanged lexical/MLP objective. Public contexts use identity positive views, with no augmentation robustness claim. The authored JavaScript reference retains parameter-renaming views. Settings for each execution are stored in its report.

## Task and unit of analysis

The positive class (`label=1`) denotes a vulnerability under the example's stated assumptions. `label=0` denotes the corrected counterpart under those assumptions; it does not mean universally safe code. Each pair shares a group, split and CWE. The authored reference split is fixed before fitting: 12 training pairs, six validation pairs and six test pairs.

No snippets are executed. This is classification and representation analysis, not dynamic exploit validation. Data audit checks exact identifiers, pair integrity, groups and whitespace-normalized duplicate strings. It does not detect semantic clones. Removing whitespace can also conflate literals that differ only in whitespace; this is a conservative heuristic, not a JavaScript equivalence test.

## Features and models

The lexical tokenizer emits JavaScript-like identifiers, operators, string/template markers and number markers. Comments are dropped; literals are normalized. Unigrams and bigrams form a vocabulary of at most 1,600 features, selected by document frequency with deterministic tie breaking. Vocabulary and smoothed IDF are fitted on **training originals and their training views only**.

For token count `c`, term frequency is `1 + log(c)`. IDF is `log((1 + N)/(1 + document_frequency)) + 1`. The vector is L2-normalized. This lightweight tokenizer is neither a parser nor a taint engine, and normalization can erase security-relevant literal details.

The linear baseline learns logistic classification on these vectors. The encoder is a 48-unit `tanh` hidden layer followed by a 16-dimensional projection, smoothed L2 normalization and a logistic classification head. All calculations use NumPy float64. Adam uses a learning rate of 0.012, beta values 0.9 / 0.999 and epsilon 1e-8; the reference run uses 240 full-batch updates. L2 weight regularization is 1e-4. Recorded loss values are measured immediately before the listed update, while reported predictions use the final updated weights.

## Positive views and negatives

Each original has an authored view renaming the local `input` parameter to `incomingValue`. In the fixture context, the snippets do not inspect source text or rely on that local parameter name. The view is label-preserving under the same assumptions. This narrow transformation does not establish arbitrary refactoring invariance.

For normalized representation `z_i`, the matching view `p(i)` is the positive. The candidate set `A(i)` contains that view and all opposite-label examples/views. Self-comparisons and non-paired examples of the same label are excluded. A vulnerable example and its corrected sibling are therefore **negatives**, never positives.

\[
L_{contrastive} = -\frac{1}{2N}\sum_{i=1}^{2N}
\log \frac{\exp(z_i^\top z_{p(i)}/\tau)}{\sum_{j\in A(i)}\exp(z_i^\top z_j/\tau)},\qquad \tau=0.15.
\]

This is a masked, paired InfoNCE / multiple-negatives-ranking-style objective implemented independently. It is not a claim to reproduce any particular library loss. Every anchor has one positive, and each batch contains both classes. The CPU implementation intentionally caps training at 512 originals because the pairwise term has quadratic memory cost.

## Security-weighted classification

With logit `s_i`, label `y_i` and vulnerable-class weight `w`, the classification term is

\[
L_{class}=\frac{\sum_i a_i\,[\operatorname{softplus}(s_i)-y_i s_i]}{\sum_i a_i},\qquad
a_i=\begin{cases}w & y_i=1\\1 & y_i=0.\end{cases}
\]

The combined objective is `L_class + lambda * L_contrastive + L2`. The four variants use `(lambda,w)` values `(0,1)`, `(0,1)`, `(0.3,1)` and `(0.3,3)`; the first is linear and the others share the MLP architecture. All models see the same training originals and renamed views. Positive weighting changes the cost of classification errors; it does **not** mathematically guarantee a smaller false-negative rate after threshold selection. These hyperparameters are preselected demonstration settings, not an optimized search.

The full weighted objective is checked against central finite differences for every parameter of a small encoder. A separate analytical contrastive example checks the candidate mask. Test inputs and reference results are in `tests/test_models.py`.

## Operating point and evaluation

Classify as vulnerable when `score >= threshold`. On validation, choose the threshold with maximum recall satisfying FPR <= 0.20. Ties prefer lower FPR, then the threshold nearest 0.5, then the larger threshold. Candidate thresholds include observed scores and their immediate floating-point successors toward 1, plus 0, 0.5 and 1. If no threshold in [0,1] is feasible, fail explicitly. Freeze the selected threshold before computing test metrics.

Report TP, TN, FP, FN, precision, recall, F1, FNR, FPR, accuracy, Brier score, average precision and ROC AUC. Precision and rates with zero denominators are `null`, not invented zeroes. Average precision is the step-weighted sum of precision over recall increments; ROC AUC uses trapezoids. Tied scores move together. The interface recomputes operating-point metrics from raw predictions and is tested against the Python implementation.

The JSON report includes 95% Wilson intervals for FNR and FPR. Those simple binomial intervals do not account for scenario or stylistic dependence, and should not be read as population-level uncertainty on this fixture collection. The public study adds repository grouping and resampling; its Wilson bands remain descriptive, and probability calibration is not established.

The threshold slider is exploratory. It changes the current view only; exported JSON preserves the original validation-selected experiment. Selecting a favorable test threshold is not valid model selection.

## Stability and embedding views

Stability measures prediction agreement, both-views-correct rate, mean absolute score change and flip counts. Agreement alone can be high when both predictions are wrong. PCA is fitted on training representations and then applied to all splits. The linear baseline's representation is its lexical feature vector; the MLP's representation is its learned normalized embedding. Plots aid inspection and are not additional validation evidence.

## References and implementation boundaries

- [Sentence Transformers: MultipleNegativesRankingLoss](https://www.sbert.net/docs/package_reference/sentence_transformer/losses.html#multiplenegativesrankingloss) — related objective family, not a code dependency.
- [NumPy random Generator](https://numpy.org/doc/stable/reference/random/generator.html) — reference RNG interface.
- [Hugging Face Auto classes](https://huggingface.co/docs/transformers/model_doc/auto) — optional complete classification-checkpoint import.
- [Semgrep taint analysis](https://semgrep.dev/docs/writing-rules/data-flow/taint-mode/overview) — optional static-analysis extension context.

No improvement over pretrained language models, real-world exploit discovery or deployment safety is claimed.
