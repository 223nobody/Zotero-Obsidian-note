# Domain Template: Agent Skills / Skill Ecosystems

Use this reference for papers about agent skills, skill packages, `SKILL.md`, skill libraries, skill retrieval/selection, skill composition, skill evolution, trace-derived skills, skill maintenance, skill governance, skill safety, visual/latent skills, or benchmarks for skill-augmented agents.

This domain should be read more narrowly than general LLM-agent work. A "skill" is not just an ability claim. Identify the concrete reusable artifact, how it is selected or loaded, how it changes the agent trajectory, and what evidence shows the change is real.

## Paper Type First

Classify the paper before drafting; the same Figure/Table can mean different things in different skill papers.

- Skill synthesis / generation: creates skills from tasks, traces, prompts, demonstrations, documents, or virtual tests.
- Skill retrieval / selection: chooses which skills to load or call from a library, graph, registry, or memory.
- Skill composition / routing: combines skills, detects dependencies/conflicts, or plans over skill graphs.
- Skill optimization / evolution: updates skill packages from failures, contrastive successes, rewards, verifier feedback, or online experience.
- Skill internalization / representation: turns text skills into latent weights, LoRA adapters, policy skills, visual skills, or other non-text artifacts.
- Skill benchmark / evaluation: measures whether agents can use, create, compose, or transfer skills.
- Skill governance / maintenance: detects drift, updates stale skills, manages library quality, or enforces contracts.
- Skill safety / security: studies malicious skills, dependency steering, unsafe composition, permission frameworks, registry attacks, or user comprehension.

## What To Identify

- Skill object: `SKILL.md`, structured skill package, references/resources, prompt snippet, tool/function library, graph node, visual binding, latent adapter, policy module, or benchmark task skill.
- Lifecycle stage: collection, recommendation, retrieval, selection, composition, execution, evaluation, distillation, optimization, evolution, maintenance, governance, or security audit.
- Agent setting: coding agent, web agent, terminal agent, embodied/VLM agent, data-science agent, clinical reasoning agent, game agent, multi-agent cooperation, or general tool-use agent.
- Runtime interface: search/show, retriever/reranker, planner/actor/critic, verifier, patcher, memory, registry API, tool schema, permission gate, or sandbox.
- Feedback signal: task success/failure, execution trace, contrastive success, verifier result, LLM-as-a-judge score, environment reward, human audit, static scan, runtime monitor, or registry metadata.
- Skill boundary: what is always loaded, what is conditionally loaded, what remains in files/resources, what becomes callable code/tool, and what is learned into model weights.
- Evaluation target: reward/pass rate, retrieval MRR/Recall@K, tool-call validity, trace divergence, transfer, robustness, token/cost/latency, safety risk, maintenance effort, or human-audited validity.

## Skill Lifecycle Reading Frame

For group-meeting notes, explain skill papers through this chain when possible:

```text
source evidence -> skill artifact -> selection/loading -> agent execution -> feedback/evaluation -> update/governance
```

Use this chain to avoid vague summaries. For example:

- A retrieval paper is not only "better retrieval"; it changes what the agent sees before acting.
- An evolution paper is not only "reflection"; it defines what counts as loss evidence and how updates are committed.
- A safety paper is not only "dangerous skills exist"; it separates candidate risk, realized tool-call behavior, and governance failure.
- A benchmark paper is not only "new tasks"; it defines what skill capability is observable and how confounders are controlled.

## Innovation Questions

- What exact skill lifecycle step does the paper improve, and what old failure mode does it target?
- Is the contribution a method, benchmark, system, registry analysis, security measurement, lifecycle framework, or taxonomy?
- What is the unit of improvement: one skill, a skill package, a skill library, a skill graph, an agent trace, a registry, or a deployed ecosystem?
- Does the method learn reusable procedures, or does it append task transcripts, examples, prompt patches, or benchmark-specific hacks?
- What prevents negative transfer: typed relations, verifier gates, role filtering, conflict detection, capability constraints, permission checks, rollback, or human/LLM audit?
- Does the result come from better skills, stronger base models, richer tools, more context, more test-time compute, more samples, better verification, or cleaner evaluation?
- What part would break if the skill library grows by 10x, the task distribution shifts, tools change, or malicious skills enter the ecosystem?

## Evidence Map

Tie each major claim to the right kind of evidence.

| Claim type | Strong evidence | Weak evidence / caution |
| --- | --- | --- |
| Skill improves capability | held-out task gains plus ablation showing skill component matters | pass rate only, no trace or ablation |
| Skill changes behavior | trace/tool-call/action analysis, trajectory alignment, retrieved skill usage | final answer score only |
| Retrieval/selection works | Recall@K/MRR plus downstream gains and conflict handling | retrieval metric without execution gain |
| Skill evolution works | before/after skill diff, verifier/replay, held-out transfer, cost | plausible rewritten skill text only |
| Governance works | drift detection, false positives, repair success, human audit | taxonomy or static scan only |
| Security risk is real | runtime realization, tool-call evidence, attacker capability analysis | candidate pattern count only |
| Benchmark is valid | task taxonomy, labels, splits, contamination checks, baseline fairness | many tasks but unclear ground truth |

## Figures / Tables / Formulas To Explain

- Overview/lifecycle figure: identify source data, skill artifact, selection/loading point, execution loop, feedback path, and update target.
- Skill package diagram: explain metadata, `SKILL.md`, references, scripts/tools, assets, progressive disclosure, and context budget.
- Retrieval/graph figure: explain matches, neighbors, dependencies, alternatives, conflicts, edge types, and how the agent uses them at runtime.
- Trace/audit figure: explain events, phase alignment, divergence, SIP-like behavior pattern, and what counts as skill influence.
- Optimization loop: explain executor, loss evidence, diagnoser, memory/momentum, patcher, verifier, commit rule, and rollback/validation.
- Benchmark table: separate task success from skill-specific evidence such as retrieval MRR, tool-call validity, pass-rate delta, cost, latency, and human-audited validity.
- Ablation table: identify whether retrieval, verifier, memory, skill library scale, graph relation type, update rule, prompt, or tool access drives the gain.
- Safety/security table: separate raw candidate counts, audited valid candidates, realized attacks, refusals, false positives, and deployment assumptions.
- Formula/objective: translate reward, loss, CCR, verifier score, similarity, graph constraint, DPO/GRPO-style update, or policy objective into the lifecycle decision it controls.
- Prompt/system-message figure: explain whether it is core method, evaluation protocol, implementation detail, or appendix reproducibility evidence.

## Common Evidence Items In Existing Notes

Use these recurring patterns when writing the mixed evidence timeline:

- `Figure 1`: often motivation, lifecycle, threat model, or system overview; explain the whole agent loop, not just boxes.
- `Table 1`: often benchmark/main result/related-work positioning; explain what is being compared and whether baselines have the same skill/tool budget.
- `Objective / Loss / Score`: usually controls skill selection, skill update, verifier scoring, reward shaping, or risk calibration; explain variables as lifecycle roles.
- Prompt screenshots: explain as protocol evidence only when they affect behavior or reproducibility; do not over-treat every prompt image as a core contribution.
- Appendix tables: usually splits, hyperparameters, prompt templates, or extra audits; compress unless they change the main conclusion.
- Case studies: explain whether the example is representative evidence, selected success, failure mode, or interpretability aid.

## Evidence Boundaries

- Pass rate alone is not enough. Prefer trace-level, retrieval-level, tool-level, verifier-level, or audit-level evidence that the skill actually changed behavior.
- A skill can improve average reward while causing negative transfer. Check per-task, per-capability, per-difficulty, or per-domain breakdowns.
- More retrieved skills are not always better. Check context budget, conflict handling, redundancy, and whether the agent can ignore irrelevant skills.
- LLM-generated skills may look plausible but need verifier, replay, human audit, held-out tasks, or runtime evidence before being treated as reliable.
- Online updates should not be assumed safe. Ask how commits are validated, rolled back, deduplicated, or prevented from corrupting a shared library.
- Security/governance papers must separate candidate risk from realized behavior. A regex/capability hit is not the same as a successful malicious tool call.
- Skill evolution papers should distinguish reusable procedure learning from adding examples, trajectories, or benchmark-specific hints.
- Latent/visual skill papers must prove that the new representation preserves skill semantics, not merely that it improves one benchmark.

## Related Work Angles

- Prompting / in-context skills vs structured skill packages vs tool libraries vs graph nodes vs latent/in-weight skills.
- Retrieval-only skill use vs graph-structured selection vs verifier-guided selection vs runtime tool-call planning.
- Offline skill mining/distillation vs online self-evolution during task execution.
- Failure-driven reflection vs trace-derived diagnosis vs optimization-style update vs reinforcement learning.
- Single-agent skill learning vs shared library/ecosystem governance.
- Capability improvement papers vs benchmark papers vs maintenance/governance papers vs safety/security papers.
- Static registry analysis vs runtime realization; capability taxonomy vs actual agent behavior.
- Text-only skills vs visual skills, code skills, tool skills, environment skills, and multimodal binding protocols.

## Common Limitations

- Evaluation uses a narrow benchmark, small skill library, synthetic tasks, or a task distribution close to skill generation data.
- Baselines have weaker retrieval, fewer tools, smaller context, fewer samples, or less optimization budget.
- Skill quality is judged by the same model that generated, selected, or patched the skill.
- Online updates are committed without independent validation, replay, human audit, or rollback.
- Retrieval metrics improve but downstream task performance or trace quality does not.
- Pass rate improves but token cost, latency, file reads, tool calls, or maintenance cost becomes high.
- Safety work reports candidate risks but not runtime realization, adaptive attackers, false positives, or user-facing mitigation.
- Learned skills encode stale APIs, private environment assumptions, benchmark leakage, brittle tool names, or non-portable file paths.
- Prompt screenshots and appendix crops are treated as evidence without explaining whether they affect the method or only document implementation.

## Note-Writing Emphasis

- In the core conclusion, name the exact skill object and lifecycle stage, not only "improves agents."
- In the paper-direction field, include both the technical axis and the lifecycle axis, such as "typed skill graph / skill selection / online graph evolution".
- In innovation analysis, use the pattern: old failure mode -> proposed skill mechanism -> supporting evidence -> boundary.
- In method/system sections, keep the runtime decision path visible: what the agent sees, what it retrieves/loads/calls, what feedback arrives, and what changes later.
- In figure explanations, say whether the figure proves capability, explains mechanism, defines benchmark protocol, or only documents prompt/configuration.
- In limitations, always ask whether the skill generalizes beyond the tested task distribution and whether failures could corrupt future reuse.
- Do not include a MinerU asset index in the final note. Prompt screenshots, extra crops, and appendix assets should appear only when they are attached to a real Figure/Table/Prompt/Case Study explanation.
