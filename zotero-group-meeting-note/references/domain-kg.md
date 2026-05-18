# Domain Template: Knowledge Graphs

Use this reference for papers about knowledge graphs, knowledge graph completion, entity/relation extraction, graph representation learning, KG reasoning, ontology alignment, knowledge-enhanced language models, KGQA, or retrieval over structured knowledge.

## What To Identify

- KG setting: construction, completion, link prediction, entity alignment, relation extraction, reasoning, question answering, recommendation, or knowledge-enhanced generation.
- Graph schema: entities, relations, attributes, ontology, literals, temporal edges, hyper-relations, qualifiers, or heterogeneous node/edge types.
- Core intervention: embedding model, GNN encoder, path reasoning, rule learning, text-graph fusion, retrieval over triples, entity linking, schema alignment, or negative sampling.
- Evaluation type: MRR/Hits@K, link prediction, reasoning accuracy, QA exact match/F1, extraction quality, calibration, efficiency, interpretability, or robustness to incomplete/noisy graphs.

## Innovation Questions

- Does the paper improve graph completion, multi-hop reasoning, schema transfer, text-graph grounding, scalability, explainability, or robustness to missing/noisy facts?
- Is the contribution a new graph representation, reasoning path, neural-symbolic method, dataset, extraction pipeline, or KG-enhanced application?
- Does the method use graph structure, textual descriptions, ontology constraints, pretrained language models, or external retrieval as the main source of gain?
- Are comparisons fair with respect to graph split, inverse relation leakage, negative sampling, entity overlap, and textual side information?

## Figures / Tables / Formulas To Explain

- KG pipeline figure: explain entity linking, triple extraction, graph construction, indexing, retrieval, reasoning, and generation/answering steps.
- Model architecture: explain entity/relation embeddings, message passing, path scoring, rule modules, and text encoders.
- Scoring formula: explain how triples, paths, relations, timestamps, or qualifiers are scored and optimized.
- Main result table: compare against embedding, GNN, rule-based, text-enhanced, and LLM-based baselines under the same graph split.
- Ablation: separate gains from graph structure, text descriptions, ontology constraints, retrieval, negative sampling, and pretrained models.
- Case study: explain successful reasoning paths, hallucinated facts, missing links, entity ambiguity, or schema mismatch.

## Related Work Angles

- Translational KG embeddings vs bilinear/semantic matching models vs GNN-based models.
- Neural KG completion vs symbolic/rule-based reasoning vs neural-symbolic hybrids.
- Text-only LLM knowledge vs explicit KG retrieval or grounding.
- Static KG vs temporal KG vs event/hyper-relational KG.
- Closed-world link prediction vs open-world extraction and completion.
- KGQA pipelines vs end-to-end generation with graph grounding.

## Common Limitations

- Dataset splits may leak inverse relations or near-duplicate triples.
- Link prediction metrics may not reflect real reasoning or downstream QA quality.
- Performance depends on high-quality entity linking or clean ontology design.
- Text-enhanced methods may gain from pretrained language models rather than graph reasoning.
- Scalability to large, dynamic, or noisy graphs is not demonstrated.
- Explanations may show plausible paths without proving causal contribution to the answer.
