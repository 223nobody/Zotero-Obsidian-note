# Domain Template: Machine Learning

Use this reference for papers about general machine learning, representation learning, optimization, probabilistic modeling, self-supervised learning, robustness, uncertainty, interpretability, AutoML, federated learning, or efficient learning.

## What To Identify

- Learning setting: supervised, semi-supervised, self-supervised, weakly supervised, unsupervised, online, continual, federated, transfer, or meta-learning.
- Core intervention: model architecture, objective function, optimization method, regularization, data construction, representation space, uncertainty estimate, calibration method, or evaluation protocol.
- Assumptions: data distribution, independence, stationarity, label availability, task family, model class, smoothness, convexity, or causal assumptions.
- Evaluation type: predictive accuracy, calibration, robustness, generalization, sample efficiency, compute efficiency, interpretability, or statistical significance.

## Innovation Questions

- Does the paper improve generalization, sample efficiency, optimization stability, robustness, calibration, interpretability, or deployment efficiency?
- Is the contribution a new algorithm, objective, theory, benchmark, analysis, or practical training recipe?
- Is the improvement caused by the proposed method itself, stronger data augmentation, extra compute, larger models, better tuning, or evaluation choices?
- Does the method hold under distribution shift, noisy labels, low-resource regimes, long-tail data, or different model scales?

## Figures / Tables / Formulas To Explain

- Method overview: explain data flow, representation changes, objective components, and where the new learning signal enters.
- Loss or objective formula: explain each term, weight, constraint, and what behavior it encourages or suppresses.
- Optimization figure: explain convergence, stability, sensitivity to hyperparameters, or failure regions.
- Main result table: compare fair baselines under the same data, model size, tuning budget, and evaluation protocol.
- Ablation: identify which loss term, regularizer, architecture part, data transform, or training step actually drives the gain.
- Robustness/calibration table: explain whether improvements survive distribution shift, noise, adversarial settings, or uncertainty evaluation.

## Related Work Angles

- Classical statistical learning vs deep learning vs foundation-model-era training.
- Architecture-level innovation vs objective-level innovation vs data-level innovation.
- Empirical training recipe vs theoretically motivated algorithm.
- Robustness, uncertainty, calibration, and interpretability as separate evidence dimensions.
- General-purpose algorithm vs task-specific adaptation.

## Common Limitations

- Gains depend on extra data, compute, tuning, augmentation, or larger backbone models.
- Baselines are under-tuned or use older training recipes.
- Theory uses assumptions that do not match the empirical setting.
- Improvements are small relative to added complexity or compute cost.
- Robustness and calibration claims are tested on too few shifts or noise types.
- Reproducibility depends on hidden hyperparameters, seeds, or expensive search.
