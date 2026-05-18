---
name: zotero-group-meeting-note
description: Build, expand, review, polish, and save Chinese group-meeting paper notes from the active Zotero paper, PDF, existing Zotero note, or extracted Markdown, including a post-draft content check, inline Chinese translations for recurring technical English phrases, and source-order arrangement of figure/table/formula sections. Use when the user asks for 组会分享, 文献汇报, seminar notes, paper briefing, PPT outline, oral report, figure/formula/table explanation, deep paper analysis, related-work comparison, terminology polishing, or wants synchronized Zotero and Obsidian notes with custom paths, filenames, dates, and assets.
---

# Zotero Group Meeting Note

Use this skill to produce a seminar-ready computer-science paper note, not a shallow abstract summary. Treat the paper, figures, formulas, tables, experimental data, and existing user notes as the source of truth.

## Core Goals

- Explain the paper's research problem, innovation, method/system mechanism, evidence, conclusion data, limitations, and related-work position.
- Give evidence-based explanations for key figures, tables, formulas, ablations, case studies, and conclusion numbers.
- Produce Chinese writing that a graduate student can directly use in a group meeting.
- Add a post-draft review pass that checks content quality and localizes recurring technical English phrases into readable Chinese inline translations.
- Preserve original-paper ordering inside the figure, table, and formula explanation sections while keeping their existing content format.
- Save the note to the exact requested destination, or use the default Obsidian/Zotero-compatible output contract.

## Required Workflow

### 1. Lock The Source

- Use the active Zotero paper first unless the user specifies another paper, file, note, title, date, output folder, or filename.
- Determine the best readable paper title from: user request, Zotero item title, PDF metadata, then attachment filename stem.
- If an existing note is provided, preserve useful manual comments, images, terminology, and structure while fixing gaps.

### 2. Prepare Output Paths Before Writing

- Always read `references/output.md` before writing or updating files.
- Prefer running `scripts/prepare_output.py` to create deterministic paths, date folders, note stubs, and `assets/`.
- Default Obsidian output is:

```text
~/Documents/Obsidian Vault/组会分享/<yy-M-d>/<论文标题>.md
```

- The default Obsidian filename is the readable paper title, not a lowercase slug and not `*-group-meeting-YYYY-MM-DD.md`.
- If the user specifies a custom path, filename, date, or H1 title, pass it through to `prepare_output.py`.
- Do not add YAML frontmatter or plugin signatures unless the user explicitly asks.

### 3. Read Efficiently

- Prefer structured full text when available, such as MinerU markdown, paper XML, Zotero note text, or extracted PDF text.
- At minimum, inspect: abstract/introduction, method/system design, experiments/results, related work, limitations if present, and conclusion.
- For figure/table/formula requests, inspect the surrounding paragraphs and captions instead of stopping at the abstract.
- When the paper direction is clear, load only the matching domain reference:
  - `references/domain-llm.md`
  - `references/domain-nlp.md`
  - `references/domain-cv.md`
  - `references/domain-ml.md`
  - `references/domain-rl.md`
  - `references/domain-kg.md`

### 4. Extract The Evidence

Capture at least:

- research problem and why it matters
- paper type: method, system, benchmark/dataset, analysis, theory, or application
- innovation claims and the prior-work route each claim targets
- method pipeline or system architecture
- key figures and what they prove
- key formulas and where they sit in the method
- key tables, strongest baselines, main gains, weak spots, and conclusion boundaries
- datasets, metrics, ablations, robustness/generalization/efficiency evidence, and case studies
- limitations, hidden assumptions, missing comparisons, and discussion questions
- a source-order inventory of figures, tables, and key equations using `references/source-order.md`

### 5. Draft With The Blueprint

- Read `references/blueprint.md` before drafting.
- Read `references/source-order.md` before drafting the figure, table, and formula explanation sections.
- Use the blueprint adaptively. Do not force every paper into every subsection.
- Prioritize: innovation analysis, figure/table/formula explanation, conclusion data interpretation, evidence chain, and related-work comparison.
- In `## 五、图片解释`, `## 六、表格与结论数据解释`, and `## 七、公式解释`, keep the section content and templates but arrange items strictly by their order in the original paper.
- If the user asks for a PPT outline, preserve the same analytical order but output slide titles, bullet points, figure/table placement, and oral cue lines.

### 6. Explain, Do Not Merely Restate

For every important figure, table, formula, and result:

- explain what it is
- explain why it matters
- connect it to an innovation claim or paper conclusion
- identify the evidence boundary or possible weakness
- provide a short `组会讲法` or `一句话总结`

### 7. Run A Review And Terminology Pass

- Read `references/review-pass.md` after the first full draft and before final delivery.
- Read `references/terminology.md` when translating technical terms, and prefer its standard renderings when they fit the paper.
- When full text is available as Markdown or text, consider running `scripts/extract_terms.py <source-file>` to collect recurring English term candidates before polishing.
- First review the note against the paper and `references/blueprint.md`: remove unsupported claims, mark missing evidence, fix section gaps, and trim repetition.
- Then scan for recurring technical English phrases and add inline Chinese translations on first important mention using the format `English phrase（中文翻译）`.
- Prioritize phrases that are central to the task, method, objective, system module, decision frontier, or repeated experimental comparison.
- Keep official names, benchmarks, datasets, APIs, model names, and author-defined module names in their original form when translation would hurt traceability; add a short Chinese explanation instead of forcing a literal translation.
- Use one consistent Chinese rendering per term across the whole note. Do not alternate between multiple translations for the same concept.
- Finish with a short spoken-polish pass: make dense paragraphs easier to present aloud without changing evidence or technical meaning.

## Output Quality Rules

The finished note should cover:

- core conclusion in 3-6 sentences
- why the paper is worth presenting
- paper type and research positioning
- innovation points and their supporting evidence
- method/system mechanism
- key figure explanations
- key table and conclusion-data explanations
- key formula explanations
- figure/table/formula sections arranged by original-paper order
- evidence-chain and credibility check
- comparison and connection with related work
- strengths, limitations, and failure modes
- high-frequency or paper-central technical English phrases translated inline on first key mention
- 3-5 discussion questions
- 5-8 minute speaking outline

## Interpretation Rules

### Figures

Do not paraphrase only the caption. Explain visual logic, modules, arrows, axes, colors, clusters, examples, trends, or heatmaps. State which innovation or conclusion the figure supports and whether the visualization has selection or representativeness limits.

### Tables

Do not only list numbers. Identify datasets, metrics, strongest/fair baselines, main gains, unstable settings, weak spots, efficiency costs, and whether the table really supports the paper's claim.

### Formulas

Translate symbols into natural language. State where the formula appears in the pipeline, what it computes/optimizes/proves, why the design is needed, and how it connects to the paper's innovation or results.

### Source Order

- For `## 五、图片解释`, arrange all Figure entries by their first appearance in the original paper.
- For `## 六、表格与结论数据解释`, arrange all Table entries by their first appearance in the original paper.
- For `## 七、公式解释`, arrange all key Equation / Loss / Objective / Score / Constraint entries by their first appearance in the original paper.
- Preserve the existing explanation content and template fields; reorder entries without rewriting them unless the content itself is unsupported or incomplete.
- Do not reorder these entries by importance, narrative convenience, innovation point, or evidence strength.

### Related Work

Do not write generic "better than prior work" claims. Identify the prior route, what the paper inherits, changes, combines, or leaves untested, and whether comparisons are fair and sufficient.

### Terminology And Translation

- Translate recurring technical English phrases on first key mention with the format `English phrase（中文翻译）`.
- After the first introduction, use one stable wording for the same term unless a shorter form clearly improves readability.
- If the acronym itself is the dominant surface form, keep it and translate it inline, for example `MORL（多目标强化学习）`.
- Do not force translations for author names, venues, citations, variable symbols, or official proper names whose English form is needed for identification.

### Claims And Missing Evidence

- Do not invent experimental numbers, venues, baselines, datasets, formulas, or author claims.
- If extraction is incomplete, mark `待核对原文` and name the missing figure/table/formula.
- If a value is visually inferred from a chart, state it as an inference.
- If a conclusion is plausible but not directly proven, label it as an interpretation or discussion point.

## When Upgrading An Existing Note

- Preserve useful content and images.
- Remove YAML frontmatter and plugin signatures unless the user wants them.
- Fix the output path and filename according to `references/output.md`.
- Deepen innovation, figure/table/formula, conclusion-data, and related-work sections before rewriting everything.

## Final Verification

Before reporting completion:

- Verify the note has completed the review pass in `references/review-pass.md`.
- Verify the file path matches the requested or default output contract.
- Verify the filename is readable paper-title based unless customized.
- Verify the date folder exists and `assets/` exists for Obsidian output.
- Verify the note body follows `references/blueprint.md` instead of becoming only an abstract summary.
- Verify `## 五、图片解释`, `## 六、表格与结论数据解释`, and `## 七、公式解释` follow original-paper order.
- Verify recurring technical English phrases are translated on first key mention and remain terminology-consistent.
- Report final paths and unresolved placeholders.
