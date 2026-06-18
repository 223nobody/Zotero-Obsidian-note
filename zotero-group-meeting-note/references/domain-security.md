# Domain Template: Security / Privacy

Use this reference for papers about software security, systems security, web security, cryptography applications, privacy, adversarial ML, secure protocols, malware, authentication, access control, or safety evaluation.

## What To Identify

- Threat model: attacker capability, defender knowledge, trust assumptions, assets, and security goals.
- Core intervention: detection method, defense, protocol, policy, static/dynamic analysis, fuzzing, sandboxing, privacy mechanism, or benchmark.
- Evaluation type: attack success rate, false positives/negatives, overhead, robustness, privacy leakage, proof, or real-world deployment.
- Baseline fairness: attacker budget, adaptive vs non-adaptive attacks, dataset freshness, vulnerability ground truth, and implementation access.

## Innovation Questions

- Does the paper improve security, privacy, usability, deployability, or measurement fidelity?
- Is the contribution a new attack, defense, analysis tool, proof, dataset, or empirical measurement?
- Which assumptions are essential: trusted hardware, honest parties, non-collusion, static attacker, secret randomness, or clean training data?
- Does the defense survive adaptive attackers and realistic deployment constraints?

## Figures / Tables / Formulas To Explain

- Threat-model diagram: explain actors, trust boundary, assets, attacker actions, and defender controls.
- Attack pipeline: explain preconditions, exploit chain, observability, and success criterion.
- Defense architecture: explain detection point, enforcement point, update path, and bypass surface.
- Result table: compare attack success, false positive rate, overhead, and robustness under fair attacker budgets.
- Privacy/security formula: explain leakage, advantage, entropy, differential privacy parameters, or proof condition.
- Case study: explain whether examples are representative or selected successes.

## Related Work Angles

- Attack papers vs defense papers vs measurement papers.
- Formal guarantee vs empirical robustness.
- Static analysis vs dynamic monitoring vs runtime enforcement.
- Privacy mechanism vs utility preservation.
- Security claim under adaptive vs non-adaptive adversaries.

## Common Limitations

- Threat model is weaker than real attackers or excludes important capabilities.
- Evaluation lacks adaptive attacks, transfer attacks, or fresh vulnerabilities.
- Dataset labels are noisy, stale, or biased toward known families.
- Overhead, usability, false positives, and deployment friction are underreported.
- Formal guarantees rely on assumptions that the implementation may violate.
