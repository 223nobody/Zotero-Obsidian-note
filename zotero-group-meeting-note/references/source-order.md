# Source Order Rules

Use this file before drafting or upgrading `## 五、图表公式解释`.

## Goal

Keep figure, table, formula, loss, objective, score, and constraint explanations aligned with the original paper's reading order. The final note should use one mixed evidence timeline, while each item still keeps the explanation template that matches its type.

## Build A Unified Inventory

Before drafting the unified evidence timeline, create a private inventory from the paper, `paper-search-mcp` source pack, extracted Markdown, Zotero note, or PDF text:

| order | type | label | first location | section | region | asset path | source role | caption / nearby text | status | core level | rationale | final entry style |
| ----- | ---- | ----- | -------------- | ------- | ------ | ---------- | ----------- | --------------------- | ------ | ---------- | --------- | ----------------- |
| 1 | Figure | Figure 1 | page/section/line | Method | main | assets/figure-01-paper-token-topic.png | object / caption / prose_reference | <caption> | available / missing | core / non-core | <why> | full / compressed |
| 2 | Equation | Equation 1 | page/section/line | Method | main | assets/equation-1.png / <none> | caption | <nearby method text> | available / missing | core / non-core | <why> | full / compressed |
| 3 | Table | Table 1 | page/section/line | Experiments | main | assets/table-1.png | caption | <caption> | available / missing | core / non-core | <why> | full / compressed |

Use the inventory to write the final note. Do not include this inventory in the final note unless the user asks for it.

When `paper-search-mcp` parsed artifacts are available, first read `references/mcp-paper-search.md`. Use `content_list.json` for block/page order and parser-provided asset paths, `full.md` for readable captions and nearby paragraphs, and `assets_dir` for local image/table/formula files. Prefer running `scripts/build_evidence_manifest.py <content_list_path> --assets-dir <assets_dir> --full-md <full_md_path>` as the first-pass structured inventory. Run `scripts/extract_source_order.py <full_md_path>` only as a Markdown fallback or as a second opinion for low-confidence manifest rows.

When only source text is available, prefer running `scripts/extract_source_order.py <source-file>` to get a first-pass inventory, then correct `region`, `asset path`, `source role`, `core level`, `rationale`, and `final entry style` by reading captions, nearby paragraphs, contribution statements, and experiment conclusions.

An inventory row represents a paper evidence item, not an asset file. One evidence item may bind zero, one, or multiple asset files; one asset file may be ignored if it is a duplicate, page header/footer, bibliography crop, isolated layout crop, or cannot be tied to a real paper item.

Field meanings:

- `region`: `main` for main-paper content, `references` for the bibliography itself, `post_reference` for content after References/Bibliography, and `appendix` for appendix/supplementary content that appears before references. Main-paper items normally come first.
- `asset path`: the matched local image/formula/table crop that should be placed under this evidence entry. Use `<none>` only when no matching asset exists. If multiple crops belong to one figure, separate them with semicolons. Do not create inventory rows just to account for every file in `assets_dir`.
- `source role`: `object` means a Markdown image/object line, `caption` means the object's own caption or label line, `caption_candidate` means a short label-like line that needs checking, and `prose_reference` means regular text that mentions an item.
- `core level`: a first-pass judgment of whether the item deserves full explanation.
- `final entry style`: `full` for complete template explanation, `compressed` for one-paragraph or bullet explanation.

## Ordering Rules

- In `## 五、图表公式解释`, mix Figure / Table / Equation / Loss / Objective / Score / Constraint entries by their first appearance in the original paper.
- With `paper-search-mcp` sources, prefer `content_list.json` block order/page sequence for first appearance. Use `full.md` heading and caption order as a fallback when structured block order is incomplete.
- If `build_evidence_manifest.py` produced a manifest, use its `region`, `block_index`, `matched_asset`, and `match_confidence` fields as the first-pass ordering and asset-binding guide; correct uncertain rows by reading the source text.
- Put only `main` region evidence in `## 五、图表公式解释` by default.
- Do not analyze `references` region evidence. If a bibliography entry contains the words Figure, Table, or Equation, ignore it as citation text.
- Put `appendix` and `post_reference` supplementary evidence that sits outside the main-paper argument in `## 八、参考文献后内容与补充材料` after the strengths/limitations/discussion section.
- Do not group all figures first, then all tables, then all formulas.
- Prefer `object`, `caption`, or `caption_candidate` locations for ordering. Treat `prose_reference` as a pointer to find the actual object, not as the final item location.
- Place each matched `asset path` under the corresponding evidence entry. Do not move matched assets into a generic appendix index, and do not create a final appendix only to list unmatchable or duplicated assets.
- Match assets in this priority order: parser-provided `content_list.json` asset fields, Markdown links near the caption/object, same-page or adjacent-block clues, filename/alt-text clues, then explicit `未匹配图片` / `待核对图片`.
- Preserve each item's explanation content and type-specific template structure when upgrading an existing note. Reorder first, then edit only where evidence, terminology, image links, or formatting need repair.
- Do not sort by importance, narrative flow, innovation point, result strength, or how often the paper cites the item later.
- Keep original labels visible, such as `Figure 1`, `Table 2`, `Equation 3`, `Loss`, or `Objective`.
- Core/non-core status controls explanation depth only; it must not change the mixed original-paper order.

## Compression Rules

Before writing, label each item as `core` or `non-core`, then compress without losing labels:

- Core evidence gets full explanations. Non-core evidence gets compressed explanations unless the user asks for exhaustive detail.
- Fewer than 10 items: full explanations for core items; compressed explanations are still allowed for clearly secondary items.
- 10-25 items: full explanations for core items and compressed explanations for non-core items.
- More than 25 items: full explanations for core items; combine consecutive related non-core items when appropriate, but mention every label and preserve the mixed original-paper order.

## Core Evidence Heuristics

Treat an item as core when it directly supports a main claim, contribution, method mechanism, or conclusion:

- Overall method/system figures, architecture diagrams, and key process diagrams.
- Objectives, loss functions, scoring formulas, theoretical conditions, or algorithm steps that carry the main technical idea.
- Main result tables, strongest-baseline comparisons, key ablations, and efficiency/robustness/generalization tables used for headline claims.
- Items repeatedly referenced in the abstract, introduction contributions, method core paragraphs, experiment conclusion, or conclusion section.
- Items that answer why the method works or whether the paper's strongest conclusion is justified.

Treat an item as non-core when it is mainly auxiliary: repeated trend plots, supplementary statistics, implementation detail tables, appendix expansions, or visuals that are descriptive but not central to the claim.

## Ambiguous Cases

- If a figure/table/equation is referenced in prose before it physically appears, order it by the caption/object's first appearance, not by the earlier prose reference.
- If `content_list.json` and `full.md` disagree, prefer the order that matches page/block sequence and mark uncertain asset bindings as `待核对`.
- If extraction loses page or line locations, fall back to the paper's numbering order and mark `顺序依据：编号推断` in the internal self-check.
- If numbering is inconsistent, duplicated, or reset in appendices, preserve main-paper items first and put appendix/supplementary or post-reference items in `## 八、参考文献后内容与补充材料` unless the user asks for appendix-first coverage. This section is still evidence-oriented; it is not an overflow area for unmatched assets.
- If a table or equation is embedded inside a figure, explain it in the Figure entry unless the paper separately labels it as a table or equation.
- If an equation is unnumbered but clearly central, label it descriptively, such as `Objective：training loss` or `Score：retrieval score`, and place it by first appearance.
- If an image crop has no label, match it to the nearest caption, heading, or numbered mention within a small neighborhood. If no reliable match exists, record it as `未匹配图片` in an internal checklist or external manifest only; do not place it in the final note or supplementary section.
- The supplementary section is for real paper content after References/Bibliography, not for MinerU asset auditing. A final note must not include `## 附录：MinerU 图片资源完整性索引`, `MinerU asset`, `MinerU extra crop`, or a filename-only asset dump.

## Strict Evidence Gate Rules

Use these rules when running batch or final-note validation:

- Manifest rows marked `required_in_final=true` must appear in the final note unless they are explicitly marked `寰呮牳瀵瑰師鏂囷細<label>`.
- Main-region required evidence must appear in the main mixed evidence timeline specified by `references/blueprint.md`; appendix or post-reference evidence must not be mixed into that main timeline.
- Strict mode fails when main-region Figure / Table / Equation / Algorithm / Prompt / Case entries are reordered against manifest order.
- A matched asset must appear in the local window for its evidence item, not only in a later appendix or resource index.
- Missing matched images, misplaced matched images, missing labels, and caption-only explanations are evidence gate failures.
- Unmatched parser images remain in the manifest or audit report. They must not be added to the final note just to improve asset counts.

## Final Check

Before delivery, compare `## 五、图表公式解释` and `## 八、参考文献后内容与补充材料` against the inventory or evidence manifest and verify that no item was moved to support a smoother narrative at the cost of original-paper order, every matched asset appears in its corresponding evidence entry, and unmatched assets were kept out of the final note unless the user explicitly requested an asset audit. If a user asks for an audit, put it in a separate manifest file, not in the seminar note.
