# Domain Template: LLM / Agents / RAG

Use this reference for papers about large language models, retrieval-augmented generation, agents, tool use, prompting, reasoning, alignment, evaluation, or LLM applications.

## What To Identify

- Model setting: closed-source API, open-source model, fine-tuned model, inference-only method, agent framework, or system pipeline.
- Core intervention: prompt design, data construction, training objective, retrieval, memory, planning, tool calling, verifier, reranker, preference optimization, safety filter, or benchmark.
- Evaluation type: automatic metrics, human evaluation, benchmark score, win rate, faithfulness, factuality, robustness, safety, latency, cost, or tool success rate.
- Baseline fairness: model size, context length, prompting budget, retrieval corpus, tool availability, number of samples, and decoding settings.

## Innovation Questions

- Does the paper improve capability, reliability, controllability, efficiency, safety, or evaluation?
- Is the contribution a new method, a new benchmark, a system integration, or an analysis of existing behavior?
- Is the gain from better prompts/data, stronger models, more test-time compute, retrieval quality, or agent orchestration?
- Does the method require privileged tools, private datasets, expensive inference, or heavy manual annotation?

## Figures / Tables / Formulas To Explain

- Architecture or agent loop: explain state, memory, planner, executor, tool interface, verifier, and feedback loop.
- Prompt or data pipeline: explain how examples are selected, transformed, filtered, and evaluated.
- Benchmark table: compare model family, parameter size, inference budget, and whether baselines use the same tools or retrieval.
- Ablation: identify which component actually drives the improvement.
- Cost/latency table: explain whether accuracy gains are worth the extra tokens, calls, or compute.
- Alignment or preference formula: translate reward, loss, KL, ranking, or policy update into natural language.

## Related Work Angles

- Prompting vs fine-tuning vs retrieval vs tool-use vs agent workflow.
- RAG systems: retriever, chunking, reranking, generator, citation/faithfulness, long-context alternatives.
- Reasoning methods: chain-of-thought, self-consistency, tree/graph search, verifier-guided decoding.
- Alignment methods: SFT, RLHF, DPO-style objectives, rejection sampling, constitutional/safety tuning.
- Evaluation work: whether the benchmark measures real ability or leaks artifacts from data construction.

## Common Limitations

- Baseline uses weaker models or less inference budget.
- Results depend on a proprietary model, prompt, retriever, or hidden dataset.
- Human evaluation protocol is small or underspecified.
- Benchmark may be contaminated, overfitted, or too narrow.
- Agent success hides high cost, long latency, brittle tool calls, or poor failure recovery.
- Faithfulness and citation quality are not directly measured.
