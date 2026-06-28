# Review Pass

Use this file after a full first draft exists and before final delivery. The goal is to turn a solid draft into a seminar-ready note that is fact-checked, terminology-consistent, and easier to speak aloud in Chinese.

## Pass 1: Content Check

Review the draft against the paper, extracted Markdown, existing note, and `references/blueprint.md`.

- If `paper-search-mcp` was used, also review against the source pack in `references/mcp-paper-search.md`: `full.md`, `content_list.json`, `manifest.json`, and `assets_dir`.
- If an evidence manifest from `scripts/build_evidence_manifest.py` exists, review against it before relying on Markdown proximity. Low-confidence rows should either be corrected from the source text or marked `待核对`.
- Remove or soften any claim that is not directly supported by the paper.
- Mark missing material as `待核对原文：Figure X / Table Y / Equation Z` instead of guessing.
- Check that each innovation point is tied to evidence such as a figure, table, formula, ablation, or case study.
- Check that the note still follows the main line of `问题 - 创新 - 机制 - 证据 - 边界`.
- Trim repeated explanations that say the same thing in abstract, innovation, and conclusion sections.
- Check that the strongest result tables, most important figures, and key formulas are not missing from the final note.
- Check that `## 五、图表公式解释` mixes Figure / Table / Equation / Loss / Objective / Score / Constraint entries by the original paper's first-appearance order.
- Check that each Figure / Table / Equation entry uses the matched local `assets/...` image or formula/table crop when available, and that the image appears under the correct entry rather than in a generic resource appendix.
- If the source came from `paper-search-mcp`, check asset binding against `content_list.json` and `get_paper_assets` / `assets_dir`, not only against Markdown proximity. Treat `assets_dir` as a candidate pool; do not fail the note merely because unrelated or duplicate parser crops are absent from the final text.
- Check that high/medium-confidence manifest rows with matched assets appear in the corresponding final-note evidence entries, unless the row was intentionally corrected after source review.
- If the draft contains `## 附录：MinerU 图片资源完整性索引`, `MinerU asset`, `MinerU extra crop`, or a filename-only list of `assets/...` images, treat this as a failed review. Delete the asset-audit section. Move any genuinely relevant image into its matching Figure / Table / Equation / Prompt / Case Study entry; keep all other unmatched assets out of the final note or, when explicitly needed, in a separate manifest/checklist file.
- Check that Obsidian wiki embeds such as `![[Pasted image ...]]` have been copied into the note's `assets/` folder and rewritten as relative Markdown links unless the user explicitly wants vault-global links.
- Check that material after References/Bibliography is not mixed into the main evidence timeline. If it contains Appendix, Supplementary Material, prompts, case studies, implementation details, checklists, or extra figures/tables/equations, put it under `## 八、参考文献后内容与补充材料`. Do the same for appendix/supplementary material before References when it is clearly outside the main-paper argument.
- Check that bibliography entries themselves are not summarized as post-reference content and that Figure/Table words inside citations are ignored.
- Check that core evidence uses full explanations and non-core evidence uses compressed explanations without dropping labels.
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

## Pass 4: Structural Output Validation

After the note has been written to disk, run:

```powershell
python scripts/validate_note.py "<note-path>"
```

Treat any error as a failed review. Fix the note and rerun the script. Warnings should be resolved when they indicate broken local links, stale wiki embeds, or supplementary sections in the wrong place; otherwise report the remaining warning briefly.

## Final Note Gate Review

For `single-final` and `batch-final-controlled`, record a gate decision before delivery:

```text
pass | needs_minor_repair | needs_major_repair | needs_regeneration
```

Check these gates in order:

- `blueprint_structure`: the note follows `references/blueprint.md` as the single structure contract, keeps the required analytical line, and does not invent a parallel structure.
- `evidence_coverage`: required Figure / Table / Equation / Algorithm / Prompt / Case evidence from the manifest is present, ordered correctly, and explained rather than caption-repeated.
- `asset_status`: all final note image links are note-local `assets/...`, matched images sit beside the evidence they support, and no MinerU asset dump appears in the note body.
- `content_depth`: core conclusion, problem positioning, innovation, mechanism, results, related work, limitations, and discussion are substantive enough for a group meeting.
- `domain_consistency`: the note correctly treats the paper as method/system/survey/benchmark/security/etc. and reads the matching domain reference when available.
- `terminology`: recurring technical English phrases have stable inline Chinese explanations at first important mention.

Failure levels:

- `needs_minor_repair`: local order, terminology, formatting, or short explanation gaps.
- `needs_major_repair`: missing required evidence, hollow chapters, weak result analysis, or wrong section responsibility.
- `needs_regeneration`: wrong paper type, wrong domain, severe shallow-summary behavior, or a draft that cannot be repaired section-by-section.

Every failed gate must include the problem location, violated rule, missing evidence or source cue, and recommended repair level. Batch runs must keep this decision in the per-paper sidecar or quality report; a note that is not `pass` must not be counted as a completed final note.

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

- If `paper-search-mcp` was used, the `paper_key` is known and the source pack paths were checked or missing paths were reported.
- `full_md_path`, `content_list_path`, and `assets_dir` exist when the MCP parser reported them.
- If `content_list_path` exists, `scripts/build_evidence_manifest.py` was run or the reason for skipping it is reported.
- The draft has no obvious unsupported claims or missing-evidence gaps left unmarked.
- Core figures, tables, formulas, and conclusion numbers are all covered.
- The unified figure/table/formula evidence timeline follows the original paper order.
- Matched images, tables, and equation crops are placed beside the evidence entries they belong to.
- Every final note image link resolves to a file in the note-local `assets/` folder, especially for images copied from MCP `assets_dir`.
- The final note contains no MinerU image resource-completeness appendix and no raw asset dump.
- `scripts/validate_note.py <note-path>` passes, or every remaining error is explicitly reported.
- Any post-reference appendix/supplementary content is handled in its own supplementary section after strengths/limitations/discussion.
- Core and non-core evidence are distinguished, with appropriate explanation depth.
- Recurring technical English phrases have inline Chinese translations at first key mention.
- The same term is not translated in two or three different ways across the note.
- The final wording still reads like a graduate student's seminar note, not a stitched glossary.
