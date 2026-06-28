---
name: zotero-group-meeting-note
description: Build, expand, review, polish, and save Chinese group-meeting paper notes from the active Zotero paper, PDF, paper-search-mcp parsed cache, existing Zotero note, or extracted Markdown, including a post-draft content check, inline Chinese translations for recurring technical English phrases, and source-order arrangement of a unified figure/table/formula evidence timeline. Use when the user asks for 组会分享, 文献汇报, seminar notes, paper briefing, PPT outline, oral report, figure/formula/table explanation, deep paper analysis, related-work comparison, terminology polishing, or wants synchronized Zotero and Obsidian notes with custom paths, filenames, dates, and assets.
---

# Zotero Group Meeting Note

Use this skill to produce a seminar-ready computer-science paper note, not a shallow abstract summary. Treat the paper, figures, formulas, tables, experimental data, and existing user notes as the source of truth.

## Core Goals

- Explain the paper's research problem, innovation, method/system mechanism, evidence, conclusion data, limitations, and related-work position.
- Give evidence-based explanations for key figures, tables, formulas, ablations, case studies, and conclusion numbers.
- Produce Chinese writing that a graduate student can directly use in a group meeting.
- Add a post-draft review pass that checks content quality and localizes recurring technical English phrases into readable Chinese inline translations.
- Preserve original-paper ordering in a unified figure/table/formula evidence timeline while keeping the appropriate explanation format for each item type.
- Save the note to the exact requested destination, or use the default Obsidian/Zotero-compatible output contract.
- Prefer `paper-search-mcp` parsed artifacts when available, using MinerU `full.md`, `content_list.json`, `manifest.json`, and `assets/` as a structured source pack.

## Production Modes

- `single-final`: generate one complete final seminar note for one paper.
- `batch-final-controlled`: generate multiple final seminar notes, but process each paper as an isolated unit and require source, blueprint-structure, evidence, asset, quality, domain-consistency, and delivery gates before marking it complete.

For final seminar notes, use `references/blueprint.md` as the single source of truth for note structure and section responsibilities. Do not create or follow a parallel final-note structure. Batch mode must enforce the same blueprint through validation gates.

For `batch-final-controlled` runs, each paper must have its own source pack, evidence manifest, note path, assets directory, validation report, quality report, and repair status. Batch mode may directly produce final notes, but only notes that pass all gates may be counted as complete.

## Rule Precedence

When instructions appear to compete, resolve them in this order:

1. Paper semantics outrank parser artifacts: a final evidence item is a paper-labeled or context-confirmed Figure / Table / Equation / Loss / Objective / Prompt / Case Study, not every image file emitted by MinerU.
2. Original-paper order outranks narrative convenience: main-paper evidence belongs in `## 五、图表公式解释`; bibliography text is ignored as evidence.
3. Matched assets belong beside the evidence they support. Unmatched, duplicate, header/footer, bibliography, or no-caption crops stay out of the final note and may appear only in an internal checklist or external manifest.
4. Supplementary content is separate from asset auditing: real appendix/supplement/prompt/case-study/checklist content belongs in `## 八、参考文献后内容与补充材料`; MinerU resource-completeness indexes do not.
5. Output rules outrank style preferences: final Obsidian links must use note-local relative `assets/...` paths, not absolute MCP cache or MinerU sidecar paths.

## Required Workflow

### 1. Lock The Source

- Use the active Zotero paper first unless the user specifies another paper, file, note, title, date, output folder, or filename.
- Determine the best readable paper title from: user request, Zotero item title, PDF metadata, then attachment filename stem.
- If an existing note is provided, preserve useful manual comments, images, terminology, and structure while fixing gaps.
- If `paper-search-mcp` is available or the user provides a title/search query/DOI/PDF path/`paper_key`, read `references/mcp-paper-search.md` and prefer the MCP parsed-cache flow before falling back to raw PDF extraction.
- Build a source pack when possible: `paper_key`, `pdf_path`, `full_md_path`, `content_list_path`, `manifest_path`, `assets_dir`, `result_zip_path`, and parser provenance. Use this source pack as the stable input for drafting and verification.
- For batch or multi-paper runs, track each paper in a JSON sidecar with `scripts/update_pipeline_sidecar.py`, or run deterministic parts with `scripts/batch_note_pipeline.py`. Use the stages `preflight -> parse_cache -> evidence_manifest -> draft -> review -> quality -> validate -> cleanup_report -> final_delivery`, and keep paths, copy maps, counts, validation results, quality decisions, repair status, and unresolved errors in the sidecar rather than in the note body.
- In batch mode, never use one paper's draft body as context for another paper. Share only the batch manifest, sidecar status, and gate reports.

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

- Prefer structured full text when available, especially `paper-search-mcp` parsed artifacts (`full.md`, `content_list.json`, `manifest.json`, `assets/`), then paper XML, Zotero note text, or extracted PDF text.
- When using `paper-search-mcp`, first recover or create parsed artifacts:
  - existing parsed paper: `list_parsed_papers`, `get_parsed_paths`, `get_parsed_paper`
  - local PDF: `parse_pdf_with_mineru(pdf_path, mode="auto")`
  - search request: `search_papers_with_elicitation` when supported, otherwise `search_papers_for_parsing` plus `parse_selected_papers`
- Use `search_parsed_papers` for targeted reading of abstract/introduction, method, equations, experiments, ablations, limitations, and appendix/supplementary material before loading large extracted files.
- At minimum, inspect: abstract/introduction, method/system design, experiments/results, related work, limitations if present, and conclusion.
- For figure/table/formula requests, inspect the surrounding paragraphs and captions instead of stopping at the abstract.
- When the source is Markdown with local image links, consider running `scripts/collect_assets.py <paper.md> --assets-dir <note-dir>/assets` to build a candidate image pool and optionally rewrite links. If the source or existing note uses Obsidian wiki embeds such as `![[Pasted image ...]]`, pass `--vault-root <vault>` when possible and rewrite them to relative `assets/...` Markdown links. Do not treat every copied candidate as final-note content.
- When the source includes `content_list.json`, use it as the first source of block order, page hints, block types, and parser-provided asset paths before relying on Markdown proximity heuristics.
- When `content_list_path` is available, prefer running `scripts/build_evidence_manifest.py <content_list_path> --assets-dir <assets_dir> --full-md <full_md_path>` before drafting. Use its output as the primary evidence/asset manifest, then correct uncertain low-confidence rows by reading `full.md` and the surrounding paper text.
- Treat manifest JSON as a private machine-readable artifact. It may include `item_key`, `asset_paths`, `asset_hashes`, `source_blocks`, `content_payload`, `panel_roles`, `page`, `block_index`, `confidence`, `region`, `source_text`, and `final_section`; do not paste it into the final note.
- After building the manifest, prefer `scripts/prepare_output.py --sync-from-manifest <manifest.json> --copy-map <copy-map.json>` so drafting uses copied note-local asset links from the copy map instead of guessing filenames.
- When the source is Markdown or extracted text, consider running `scripts/extract_source_order.py <source-file>` to create a first-pass mixed evidence inventory before drafting. Use its `asset path` column to bind images, table crops, and formula crops to the corresponding Figure / Table / Equation entries. Use `--include-mentions` only when you need to audit prose references separately from captions/objects.
- Treat `References` / `Bibliography` / `参考文献` as a boundary. Do not summarize the bibliography itself. If the paper contains appendix, supplementary, prompt, case-study, implementation, ethics, checklist, or extra evidence after the bibliography, or appendix/supplementary content that is clearly outside the main-paper argument, handle it separately after the strengths/limitations/discussion section.
- When the paper direction is clear, load only the matching domain reference:
  - `references/domain-llm.md`
  - `references/domain-nlp.md`
  - `references/domain-cv.md`
  - `references/domain-ml.md`
  - `references/domain-rl.md`
  - `references/domain-kg.md`
  - `references/domain-systems.md`
  - `references/domain-security.md`
  - `references/domain-skill.md`
  - `references/domain-db.md`
  - `references/domain-hci.md`

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
- a unified source-order inventory of figures, tables, and key equations using `references/source-order.md`
- when `content_list_path` is available, a `build_evidence_manifest.py` evidence manifest with order, region, evidence `item_key`, matched asset(s), asset hashes, source blocks, page, block index, source text, confidence, final section, and rationale
- a mapping from each paper evidence item to the best matching local image/table/formula asset, with unmatchable assets marked only in the private inventory
- when MCP parsed artifacts are available, a mapping from `content_list.json` blocks and matched `assets_dir` files to final note evidence entries; `assets_dir` itself is not a coverage checklist
- a separate inventory for appendix/post-reference supplementary evidence when the paper has substantive content outside the main-paper argument

### 5. Draft With The Blueprint

- Read `references/blueprint.md` before drafting.
- Read `references/source-order.md` before drafting the unified figure/table/formula evidence timeline.
- If using `paper-search-mcp`, read `references/mcp-paper-search.md` before drafting and keep the source pack paths available during image copying and final verification.
- If an evidence manifest was built, draft from manifest rows first: main-region rows go to `## 五、图表公式解释`; appendix/post-reference rows go to `## 八、参考文献后内容与补充材料`; low-confidence rows require nearby text verification or an explicit `待核对`.
- Use the blueprint adaptively. Do not force every paper into every subsection.
- Prioritize: innovation analysis, figure/table/formula explanation, conclusion data interpretation, and related-work comparison.
- In `## 五、图表公式解释`, arrange Figure / Table / Equation / Loss / Objective / Score / Constraint entries together by their first appearance in the original paper. Use the item-specific templates from `references/blueprint.md`, but do not split the final note into separate figure, table, and formula blocks.
- Place each matched image, table crop, or formula crop directly under its corresponding evidence entry. Do not put matched evidence images only in a final asset index.
- Never include `## 附录：MinerU 图片资源完整性索引`, `MinerU asset`, `MinerU extra crop`, or a filename-only asset dump in the final note. The note is a paper explanation, not a MinerU asset audit. Move key images into the right evidence entries and keep unmatched assets out of the final note unless the user explicitly requests an asset audit.
- If the paper has substantive content after References/Bibliography, or supplementary/appendix content that should not be mixed into the main evidence timeline, add `## 八、参考文献后内容与补充材料` after the strengths/limitations/discussion section. Put those figures, tables, equations, prompts, case studies, checklists, and implementation details there, preserving their own order and matched assets.
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
- Read `references/validation.md` when validating a written note or after changing skill scripts/references.
- Read `references/terminology.md` when translating technical terms, and prefer its standard renderings when they fit the paper.
- When full text is available as Markdown or text, consider running `scripts/extract_terms.py <source-file>` to collect recurring English term candidates before polishing.
- When the note has been written to disk, run `scripts/validate_note.py <note-path>` to catch banned MinerU asset indexes, absolute/stale image links, missing `assets/...` files, and resource-dump sections before reporting completion. If an evidence manifest exists, run `scripts/validate_note.py <note-path> --evidence-manifest <manifest.json> --copy-map <copy-map.json> --strict-evidence` for batch delivery or whenever image placement must be enforced.
- For final or batch delivery, also run `scripts/audit_note_quality.py --note <note-path> --source-pack <source-pack.json> --evidence-manifest <manifest.json> --blueprint references/blueprint.md --json` when the source pack exists. Treat `needs_minor_repair`, `needs_major_repair`, and `needs_regeneration` as unfinished states until the requested repair loop has run or the unresolved issue is reported.
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
- a unified figure/table/formula evidence timeline arranged by original-paper order
- matched local images placed beside their corresponding evidence entries
- matched MCP `assets_dir` images copied or linked through the note-local `assets/` folder when the note is saved to Obsidian
- full explanations for core evidence and compressed explanations for non-core evidence
- comparison and connection with related work
- strengths, limitations, and failure modes
- a separate appendix/post-reference supplementary section when the paper has substantive content outside the main-paper argument
- high-frequency or paper-central technical English phrases translated inline on first key mention
- 3-5 discussion questions

## Interpretation Rules

- Use `references/blueprint.md` for figure, table, formula, related-work, limitation, and speaking-outline templates.
- Use `references/source-order.md` for the unified evidence timeline and compression thresholds.
- Use `references/review-pass.md` for unsupported-claim checks, terminology localization, and spoken polish.
- Do not invent experimental numbers, venues, baselines, datasets, formulas, or author claims.
- If extraction is incomplete, mark `待核对原文` and name the missing figure/table/formula.
- If an image/table/formula asset cannot be matched to a specific paper item, keep it out of the final note and mark it as `未匹配图片` or `待核对图片` only in an internal checklist or external manifest instead of inventing a Figure/Table/Equation number.
- If `content_list.json` and `full.md` disagree on order or asset binding, prefer the original-paper order visible in `content_list.json` / page sequence, then document uncertain bindings as `待核对`.
- If a figure/table/equation appears after References/Bibliography, or in appendix/supplementary material outside the main-paper argument, do not merge it into the main-paper evidence timeline. Put it in `## 八、参考文献后内容与补充材料`.
- If a value is visually inferred from a chart, state it as an inference.
- If a conclusion is plausible but not directly proven, label it as an interpretation or discussion point.

## When Upgrading An Existing Note

- Preserve useful content and images.
- Preserve clearly manual comments, TODOs, local interpretations, and question lists unless they conflict with the paper evidence.
- When an existing note already explains a figure/table/formula, keep the useful explanation and move it into the unified evidence timeline instead of rewriting from scratch.
- When an existing note has images in a generic asset appendix or Obsidian wiki embeds, move matched images into their corresponding evidence entries and rewrite links to relative `assets/...` paths when possible.
- When MCP parsed artifacts are available for the same paper, use `get_parsed_paths` / `get_paper_assets` to repair missing or stale note images instead of guessing from the existing note alone.
- When an existing note mixes appendix/post-reference supplementary content into the main evidence timeline, split those entries into `## 八、参考文献后内容与补充材料`.
- Fix evidence gaps before style rewrites: missing items, unsupported numbers, broken image links, and stale terminology have priority over prose polish.
- Remove YAML frontmatter and plugin signatures unless the user wants them.
- Fix the output path and filename according to `references/output.md`.
- Deepen innovation, figure/table/formula, conclusion-data, and related-work sections before rewriting everything.

## Final Verification

Before reporting completion:

- Verify the note has completed the review pass in `references/review-pass.md`.
- Verify the file path matches the requested or default output contract.
- Verify the filename is readable paper-title based unless customized.
- Verify the date folder exists and `assets/` exists for Obsidian output.
- If using `paper-search-mcp`, verify the source pack paths exist or report which parsed artifacts are missing.
- If an evidence manifest was built, verify the final note's evidence timeline and matched image links against it; use the copy map to match copied assets by destination/hash and verify each image appears in the local section for its evidence item.
- Run `scripts/audit_note_assets.py <note-path> --output <asset-report.json>` after drafting or cleanup. Keep image link counts, total assets, unused assets, duplicate hashes, and deletion actions in that JSON report; never add an asset audit section to the final note.
- Verify the note body follows `references/blueprint.md` instead of becoming only an abstract summary.
- Verify `## 五、图表公式解释` mixes figure, table, and formula entries by original-paper order.
- Verify matched evidence images appear under the right entries rather than only in a generic appendix/resource index.
- Verify the final note does not contain `## 附录：MinerU 图片资源完整性索引`, `MinerU asset`, `MinerU extra crop`, or a raw list of `assets/...` files.
- Verify note image links resolve to files in the note-local `assets/` folder, especially when the source images came from MCP `assets_dir`.
- Verify `scripts/validate_note.py <note-path>` passes, or report its remaining errors explicitly.
- Verify the final quality status is `pass` when a quality report was generated. If it is not `pass`, report the repair level and do not count the note as a completed final note.
- Verify appendix/post-reference supplementary content is handled in `## 八、参考文献后内容与补充材料` when present.
- Verify recurring technical English phrases are translated on first key mention and remain terminology-consistent.
- Report final paths, `paper_key` when applicable, and unresolved placeholders or asset-binding gaps.
- After the note passes validation, offer to clean up intermediate artifacts per `references/output.md#post-delivery-cleanup`. Preserve: the source PDF, `<pdf>_mineru/` parsed directory, `.paper_search_cache/`, and the final Obsidian note. Delete: evidence manifest JSONs, MinerU result zip, Zotero stubs, and test files.
