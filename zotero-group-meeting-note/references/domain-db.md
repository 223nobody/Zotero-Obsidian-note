# Domain Template: Databases / Data Management

Use this reference for papers about database systems, query optimization, transaction processing, indexing, data lakes, stream processing, data integration, graph data management, or analytical engines.

## What To Identify

- Data-management setting: OLTP, OLAP, HTAP, streaming, graph, vector search, federated query, data cleaning, or data integration.
- Core intervention: index, optimizer rule, cost model, execution engine, storage layout, concurrency control, caching, compression, or benchmark.
- Workload: query mix, update rate, data size, skew, selectivity, concurrency, latency target, and hardware.
- Baseline fairness: optimizer tuning, index availability, warm/cold cache, data distribution, concurrency level, and implementation maturity.

## Innovation Questions

- Does the paper improve query latency, throughput, scalability, freshness, consistency, storage cost, or robustness to skew?
- Is the novelty in the data structure, optimizer, execution model, transaction protocol, benchmark, or system integration?
- Does the method change a classic trade-off such as reads vs writes, latency vs freshness, compression vs CPU, or consistency vs availability?
- Are gains tied to specific workloads, distributions, schemas, or hardware?

## Figures / Tables / Formulas To Explain

- System architecture: explain parser/optimizer/executor/storage boundaries and data flow.
- Query plan figure: explain operator changes, pruning, pushdown, or parallelism.
- Latency/throughput curves: explain selectivity, concurrency, data scale, and saturation.
- Benchmark table: identify workload class, best baseline, and where gains disappear.
- Cost model formula: translate variables, assumptions, and how it guides plan selection.
- Ablation: identify which index, optimizer feature, or cache policy drives the result.

## Related Work Angles

- Traditional relational systems vs specialized engines.
- Rule-based vs learned cost models or learned indexes.
- Batch analytics vs streaming/freshness-oriented processing.
- Exact query processing vs approximate or probabilistic methods.
- Benchmark representativeness and comparability with established systems.

## Common Limitations

- Workload is narrow, synthetic, or tuned to the proposed design.
- Baselines lack equivalent indexes, memory budgets, or optimizer hints.
- Update-heavy, skewed, or concurrent settings are under-tested.
- System integration complexity and maintenance cost are not discussed.
- Gains depend on hardware characteristics or data distributions not generally available.
