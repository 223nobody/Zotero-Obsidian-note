# Domain Template: Systems

Use this reference for papers about operating systems, distributed systems, storage, networking, compilers, databases-as-systems, cloud infrastructure, edge systems, or production ML systems.

## What To Identify

- System goal: throughput, latency, scalability, reliability, availability, consistency, cost, energy, memory, or developer productivity.
- Core intervention: architecture, scheduler, cache, protocol, runtime, compiler pass, storage layout, resource manager, monitoring loop, or deployment strategy.
- Workload setting: synthetic benchmark, trace replay, production workload, microbenchmark, macrobenchmark, or user study.
- Baseline fairness: hardware, cluster size, network, workload mix, configuration tuning, implementation maturity, and failure conditions.

## Innovation Questions

- Does the paper improve a bottleneck, remove a constraint, or make a new deployment feasible?
- Is the novelty in the algorithm, architecture, engineering integration, measurement, or operational policy?
- Which trade-off changes: performance vs consistency, cost vs reliability, latency vs accuracy, or simplicity vs flexibility?
- Does the method rely on assumptions about workload locality, cluster homogeneity, network behavior, or operator control?

## Figures / Tables / Formulas To Explain

- Architecture diagram: explain component boundaries, data/control flow, bottleneck location, and fault boundary.
- Timeline or pipeline figure: explain queueing, scheduling, critical path, and where latency is saved.
- Throughput/latency curves: explain workload scale, saturation point, tail latency, and stability.
- Ablation or configuration table: identify which design decision drives the main gain.
- Cost/resource table: explain CPU, memory, bandwidth, storage, energy, or operator overhead.
- Complexity or queueing formula: translate assumptions, variables, and what bound or trade-off it captures.

## Related Work Angles

- General-purpose system vs workload-specialized system.
- Centralized scheduler vs decentralized coordination.
- Stronger guarantees vs relaxed guarantees for performance.
- Measurement paper vs design paper vs production experience report.
- Whether comparisons use equivalent hardware, tuning effort, and failure models.

## Common Limitations

- Evaluation uses small clusters, narrow traces, or short runs.
- Tail latency, failures, and recovery behavior are under-tested.
- Baselines are not tuned by system experts or use old implementations.
- Gains depend on special hardware, private traces, or workload assumptions.
- Operational cost, migration difficulty, and debugging complexity are not measured.
