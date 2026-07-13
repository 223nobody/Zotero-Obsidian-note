# Error Codes

Use these codes in JSON reports, repair contexts, sidecars, and batch summaries. Do not paste them into the final note unless the user explicitly asks for an audit report.

## Quality

- `Q-MATH-FORMAT-001`: math-like symbols are written as inline code spans. Repair scope: `item_patch`.
- `Q-FORMULA-DEPTH-001`: a core Equation/Loss/Objective/Score/Constraint lacks formula visual or LaTeX, symbols, objective/constraint intuition, method position, claim/result connection, or boundary. Repair scope: `item_patch`.
- `Q-EVIDENCE-NARRATIVE-001`: a core Figure/Table/Formula/Prompt/Case entry restates the caption or template without explaining the evidence relation. Repair scope: `item_patch` or `section_patch`.
- `Q-EVIDENCE-COVERAGE-001`: a required manifest item is absent from the final note. Repair scope: `section_patch`.
- `Q-DRAFT-ARTIFACT-001`: placeholders, internal pipeline wording, or unresolved drafting text leaked into the final note. Repair scope: `section_patch`.

## Domain

- `D-PAPER-TYPE-001`: the note's explicit `论文类型` conflicts with source title/abstract cues. Repair scope: `domain_regeneration`.
- `D-SKILL-LIFECYCLE-001`: an agent-skill note does not identify the relevant lifecycle stage. Repair scope: `section_patch`.
- `D-SKILL-OBJECT-001`: an agent-skill note does not define what the paper treats as a skill object. Repair scope: `section_patch`.

## Evidence And Assets

- `V-BLUEPRINT-001`: required blueprint structure is missing or replaced by a parallel structure. Repair scope: `section_patch`.
- `V-EVIDENCE-MISSING-001`: a required manifest item is not referenced in the note body. Repair scope: `section_patch`.
- `V-EVIDENCE-MISPLACED-001`: a manifest item or asset appears in the wrong final section or outside its local evidence window. Repair scope: `section_patch`.
- `V-EVIDENCE-ORDER-001`: main-region evidence order violates the source-order manifest. Repair scope: `section_patch`.
- `A-COPYMAP-001`: a final image link is not backed by the authoritative copy map. Repair scope: `asset_repair`.
- `A-DUPLICATE-SHA-001`: note-local assets contain duplicate SHA256 files after cleanup. Repair scope: `asset_repair`.
- `A-ORPHAN-FORMULA-001`: formula-looking source crops exist but are not verified or represented in the final asset path. Repair scope: `asset_repair` or `manual_review_required`.
- `A-MULTIPANEL-001`: a structured multi-panel Figure/Table has only partial local panel coverage. Repair scope: `asset_repair` plus `section_patch`.

## Reporting Rules

- Reports should include `gate`, `code`, `severity`, `repair_scope`, `item_key`, `display_label`, `missing_slots`, `source_context`, and `required_action` when applicable.
- `needs_minor_repair`, `needs_major_repair`, `needs_regeneration`, and any non-empty `failed_gates` list are unfinished states for controlled final delivery.
- After two repair rounds, unresolved items must keep the code, item key, report paths, and next action.
