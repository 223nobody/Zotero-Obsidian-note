# Review Pass

Use this file after a full first draft exists and before final delivery. The goal is to turn a solid draft into a seminar-ready note that is fact-checked, terminology-consistent, and easier to speak aloud in Chinese.

## Pass 1: Content Check

Review the draft against the paper, extracted Markdown, existing note, and `references/blueprint.md`.

- Remove or soften any claim that is not directly supported by the paper.
- Mark missing material as `待核对原文：Figure X / Table Y / Equation Z` instead of guessing.
- Check that each innovation point is tied to evidence such as a figure, table, formula, ablation, or case study.
- Check that the note still follows the main line of `问题 - 创新 - 机制 - 证据 - 边界`.
- Trim repeated explanations that say the same thing in abstract, innovation, and conclusion sections.
- Check that the strongest result tables, most important figures, and key formulas are not missing from the final note.
- Check that `## 五、图片解释`, `## 六、表格与结论数据解释`, and `## 七、公式解释` each follow the original paper's first-appearance order.
- Prefer explicit uncertainty labels such as “推断”“讨论点”“证据不足” when the paper does not fully prove a conclusion.

## Pass 2: Terminology Localization

Scan the draft for recurring technical English phrases, especially multi-word noun phrases and paper-specific jargon.

- Prefer standard renderings in `references/terminology.md` when they fit the paper context.
- If full text is available, use `scripts/extract_terms.py <source-file>` as a lightweight candidate list before deciding what to translate.
- Translate the first important mention with the format `English phrase（中文翻译）`.
- Prioritize terms that appear at least twice, or are central to the task, method, objective, policy, frontier, system component, training setup, or evaluation claim.
- Keep one stable Chinese translation for the same term across the entire note.
- If the acronym is the dominant form in the paper, use `Acronym（中文翻译）`.
- If both the full phrase and acronym matter, introduce them once in a compact way, for example `retrieval-augmented generation, RAG（检索增强生成）`.
- Preserve official names for datasets, benchmarks, models, APIs, libraries, and author-defined module names when translation would make them harder to identify or search.
- Do not waste space translating generic academic English such as “experiment”, “baseline”, or “setting” when they are not key technical concepts.

## Translation Style Preferences

- Prefer community-standard Chinese renderings over literal word-by-word translation.
- Prefer terms that sound natural in a spoken group meeting, not only in a written survey.
- When multiple Chinese renderings exist, choose one and use it consistently.
- Keep the local sentence readable after inserting the translation. Avoid turning every clause into a glossary.

## Good Inline Examples

- `Pareto optimal policies（帕累托最优策略）`
- `Pareto Frontier（帕累托前沿）`
- `off-policy learning（离策略学习）`
- `MORL（多目标强化学习）`

## Pass 3: Spoken Polish

Make the note easier to present aloud without weakening the analysis.

- Split sentences that carry too many claims at once.
- Turn purely abstract claims into evidence-linked phrasing.
- Keep `组会讲法` lines concise enough to be read directly.
- Preserve technical terms, numbers, figure/table/equation references, and uncertainty labels.
- Do not turn the note into a PPT script; keep it as a reusable seminar note.

## Final Self-Check

Before delivery, confirm:

- The draft has no obvious unsupported claims or missing-evidence gaps left unmarked.
- Core figures, tables, formulas, and conclusion numbers are all covered.
- Figure, table, and formula explanation sections follow the original paper order.
- Recurring technical English phrases have inline Chinese translations at first key mention.
- The same term is not translated in two or three different ways across the note.
- The final wording still reads like a graduate student's seminar note, not a stitched glossary.
