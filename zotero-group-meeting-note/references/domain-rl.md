# Domain Template: Reinforcement Learning

Use this reference for papers about reinforcement learning, offline RL, online RL, model-based RL, imitation learning, preference learning, multi-agent RL, hierarchical RL, safe RL, robotics control, or multi-objective RL.

## What To Identify

- RL setting: online, offline/batch, on-policy, off-policy, model-free, model-based, imitation, inverse RL, multi-agent, hierarchical, safe, constrained, or multi-objective.
- Environment and task: simulator, real robot, game, control benchmark, recommendation setting, dialogue/agent environment, horizon, reward sparsity, observability, and action space.
- Core intervention: policy update, value estimation, world model, exploration strategy, reward design, constraint handling, preference conditioning, replay/data filtering, or planning mechanism.
- Evaluation type: return, success rate, sample efficiency, safety violations, constraint satisfaction, robustness, generalization, real-world transfer, or compute cost.

## Innovation Questions

- Does the paper improve sample efficiency, exploration, stability, safety, offline generalization, transfer, coordination, or preference controllability?
- Is the contribution a new policy/value objective, model learning method, planner, data selection rule, reward/preference formulation, or benchmark?
- Does the method rely on dense rewards, expert demonstrations, privileged state, high-quality offline data, or simulator access?
- Does the evidence separate policy improvement from environment tuning, reward shaping, data quality, or evaluation variance?

## Figures / Tables / Formulas To Explain

- Algorithm diagram: explain policy, value function, replay buffer, world model, planner, reward model, and how information flows between them.
- Objective or Bellman equation: explain target values, bootstrapping, discounting, constraints, entropy, KL, or preference weights.
- Learning curve: explain sample efficiency, variance across seeds, instability, convergence, and whether final performance or learning speed matters more.
- Offline RL table: explain dataset quality, behavior policy, coverage, conservative penalties, and out-of-distribution action risks.
- Multi-objective/preference result: explain Pareto frontier, preference vector, trade-off coverage, and whether policies adapt at test time.
- Safety or robustness table: explain constraint violations, worst-case return, distribution shift, and real-world deployment risk.

## Related Work Angles

- Model-free vs model-based RL.
- On-policy vs off-policy learning.
- Online RL vs offline RL vs imitation learning.
- Reward engineering vs preference learning vs constrained optimization.
- Single-agent vs multi-agent coordination.
- Single-objective optimization vs Pareto or preference-conditioned RL.

## Common Limitations

- Results have high variance or too few random seeds.
- Benchmarks are simulator-heavy and may not transfer to real systems.
- Offline RL performance depends strongly on dataset coverage and behavior policy quality.
- Safety claims lack stress tests, worst-case analysis, or real constraint costs.
- Exploration gains rely on privileged signals or hand-designed rewards.
- Multi-objective results show limited preference coverage or weak baselines for Pareto comparison.
