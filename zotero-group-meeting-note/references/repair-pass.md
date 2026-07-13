# Repair Pass

Use this file when any validation, quality, domain, asset, or unmatched-asset gate is not `pass`.

## Inputs

For one paper, repair may read only:

- `source_pack.json`
- `evidence_manifest.json`
- `copy_map.json`
- current note Markdown
- validation, quality, domain, asset, and unmatched-asset reports
- `references/blueprint.md`, `references/source-order.md`, `references/review-pass.md`, `references/validation.md`, and the relevant domain reference

Do not read another paper's final note body, repair report, or evidence manifest.

## Repair Scopes

- `item_patch`: repair only the named `item_key` or `display_label`.
- `section_patch`: repair one final-note section, usually `## 五、图表公式解释` or `## 八、参考文献后内容与补充材料`.
- `asset_repair`: rerun asset sync/copy-map cleanup and update only affected links.
- `domain_regeneration`: rebuild the note's reading frame, especially `论文类型`, positioning, innovation, and evidence interpretation.
- `full_regeneration`: regenerate the paper note from the source pack when local patching cannot preserve correctness.
- `manual_review_required`: keep the issue unresolved until a human or visual check resolves it.

## Required Procedure

1. Build or read the repair context with `scripts/build_repair_context.py`.
2. Sort failed items by gate severity: domain regeneration, validation/evidence coverage, formula depth, evidence narrative, asset binding, style cleanup.
3. Apply the smallest valid repair scope.
4. Rerun all final gates after every repair: quality, domain, validation, asset, and unmatched-asset checks.
5. Stop after at most two repair rounds.
6. If any gate still fails, write the item-level unresolved reason to the sidecar and batch summary.

## Item-Level Requirements

For `formula_depth`, the repaired item must include formula image or LaTeX, symbol explanation, objective/constraint intuition, method position, claim/result connection, boundary, and a meeting talk line.

For `evidence_narrative`, the repaired item must explain what the figure/table/formula shows, which claim it supports, how it connects to the method/result chain, what it cannot prove, and how to present it in group meeting.

For `paper_type_alignment`, do not merely rename the `论文类型` field. Rebuild the core framing if the wrong paper type changed the interpretation of contribution, evidence, or limitations.

## Completion

A repaired paper is complete only when all gates return `pass` and `final_delivery=pass`. A paper with generated files but non-pass gates remains unresolved.
