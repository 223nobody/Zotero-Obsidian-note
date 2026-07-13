# Validation

Use this reference when validating generated notes or after changing skill scripts/references.

## Final-Note Gate Sequence

For `single-final` and `batch-final-controlled`, validate each paper with these gates:

1. `preflight gate`: required source paths and output paths exist.
2. `source pack gate`: one paper has one isolated source pack; later reports refer back to it.
3. `evidence manifest gate`: `content_list.json` / `full.md` evidence is represented in a private manifest.
4. `blueprint structure gate`: the note follows `references/blueprint.md` as the single structure contract.
5. `evidence coverage gate`: required manifest evidence appears in the correct final sections and order.
6. `asset gate`: final note images are local, resolved, and not a parser asset dump.
7. `quality gate`: content depth is seminar-ready and not only a summary.
   - `math_format`: math-like code spans are forbidden; formulas and symbols must use LaTeX math.
   - `formula_depth`: core equations/losses/objectives need symbol, objective/constraint intuition, method/result connection, and boundary.
   - `evidence_narrative`: core figures/tables/formulas must explain the evidence relation, not only restate captions or fill repeated template headings.
8. `domain consistency gate`: paper type and domain-specific emphasis are correct.
9. `final delivery gate`: reports and sidecar status distinguish generated files from passed final notes.

Batch completion means all gates pass for that paper. A failed quality, domain, or evidence gate must trigger repair or remain in the unresolved list.

For code-level gate identifiers and repair scopes, use `references/error-codes.md`. For repair context construction and two-round repair behavior, use `references/repair-pass.md`. For controlled batch execution, source-pack quality, sidecars, and final reports, use `references/batch-control.md`. For copy-map and asset identity rules, use `references/asset-binding.md`.

## Unified Final Gate Runner

For one-paper final delivery, prefer the deterministic final gate runner after the note has been drafted and reviewed:

```powershell
python scripts/final_gate_runner.py `
  --paper-key "<paper-key>" `
  --note "<note-path>" `
  --source-pack "<source-pack.json>" `
  --evidence-manifest "<evidence_manifest.json>" `
  --copy-map "<copy_map.json>" `
  --content-list "<content_list.json>" `
  --source-assets-dir "<mineru-assets-dir>" `
  --note-assets-dir "<note-assets-dir>" `
  --reports-dir "<work-dir>/reports" `
  --sidecar "<sidecar.json>" `
  --strict-evidence `
  --copy-map-authoritative `
  --fail-on-duplicate-assets `
  --fail-on-unmatched-assets `
  --json
```

The runner creates validation, quality, domain, asset, unmatched-asset, and final-gate JSON reports for exactly one paper. It is not a drafting tool and must not be used to process multiple paper bodies in one context.
When `--source-pack` is supplied, the runner may infer `content_list` and source assets from the source pack if explicit paths are omitted. For controlled batch output, missing source assets make the unmatched-asset gate fail; do not silently skip this gate for MinerU-backed papers.
If a child gate command exits nonzero, the runner treats that report as unfinished even if the child process printed `status=pass`. The normalized report records `command_returncode` and `command_failed`, so final delivery cannot pass on a subprocess false positive.

Every report used by final delivery should expose these top-level fields when possible:

```json
{
  "schema_version": 2,
  "report_type": "quality | domain | validation | asset | unmatched_asset | final_gate",
  "status": "pass | fail | warning | needs_minor_repair | needs_major_repair | needs_regeneration | skipped",
  "ok": true,
  "failed_gates": [],
  "problem_count": 0,
  "input_paths": {},
  "input_hashes": {}
}
```

For sidecars, run:

```powershell
python scripts/validate_sidecar.py "<sidecar.json>" --write-migrated --json
```

The sidecar validator checks stage schema, report paths, artifact hashes, stale input hashes, repair-round limits, final-gate report status, final-gate paper/note identity, final-gate report path consistency, and whether `final_delivery=complete` is backed by pass-status gate reports. A report is stale when its recorded `input_hashes` no longer match the current note, source pack, evidence manifest, copy map, content list, blueprint path, note assets directory, or source assets directory.

## Per-Note Validation

After writing a note to disk, run:

```powershell
python scripts/validate_note.py "<note-path>"
```

If the note was generated from `paper-search-mcp` / MinerU and `content_list_path` exists, also build an evidence manifest before drafting or reviewing:

```powershell
python scripts/build_evidence_manifest.py "<content_list_path>" `
  --assets-dir "<assets_dir>" `
  --full-md "<full_md_path>" `
  --output "<working-evidence-manifest.json>"
```

Use the manifest to verify item order, `main` vs `appendix`/`post_reference` placement, matched assets, and low-confidence rows. Do not paste the manifest into the final note.

After preparing the Obsidian output path, copy manifest assets and write a stable copy map:

```powershell
python scripts/prepare_output.py `
  --article-filename "<paper-title-or-pdf>" `
  --obsidian-dir "<note-dir>" `
  --sync-from-manifest "<working-evidence-manifest.json>" `
  --copy-map "<copy-map.json>"
```

Use the copy map's `markdown` fields when drafting image links. It records `item_key`, source/destination paths, and SHA256 hashes so validation does not have to rely on fragile basenames.

For notes already drafted, validate structure and write a JSON report when the result is part of a batch:

```powershell
python scripts/validate_note.py "<note-path>" `
  --blueprint "references/blueprint.md" `
  --evidence-manifest "<working-evidence-manifest.json>" `
  --copy-map "<copy-map.json>" `
  --strict-evidence `
  --json > "<validation-report.json>"
```

When `--evidence-manifest` is used without `--strict-evidence`, warnings such as `missing_evidence_reference`, `missing_evidence_asset_link`, and `misplaced_evidence_asset_link` mean the note is structurally readable but does not fully satisfy evidence placement. Use `--strict-evidence` for batch delivery so those gaps fail validation.

For content-depth review, write a separate quality report:

```powershell
python scripts/audit_note_quality.py `
  --note "<note-path>" `
  --source-pack "<source-pack.json>" `
  --evidence-manifest "<working-evidence-manifest.json>" `
  --blueprint "references/blueprint.md" `
  --json > "<quality-report.json>"
```

Treat `needs_minor_repair`, `needs_major_repair`, and `needs_regeneration` as unfinished states for final delivery unless the unresolved issue is explicitly accepted and reported.

The JSON quality report should expose item-level repair context when a gate fails:

```json
{
  "schema_version": 2,
  "status": "needs_major_repair",
  "failed_gates": ["formula_depth"],
  "repair_scope": "item_patch",
  "failed_items": [
    {
      "gate": "formula_depth",
      "item_key": "main-equation-equation-10",
      "display_label": "Equation 10",
      "missing_slots": ["symbols", "objective_or_constraint", "claim_or_result_connection"],
      "diagnostics": {
        "compact_len": 180,
        "minimum_len": 260,
        "detail_hits": 1,
        "minimum_hits": 3
      },
      "current_excerpt": "...",
      "source_context": "...",
      "required_action": "Rewrite only the Equation 10 entry..."
    }
  ]
}
```

The quality report is calibrated as a content-depth gate, not an image-hash gate. It should catch shallow sections, missing required labels, wrong evidence coverage, shallow formula/equation explanations, math-like code spans such as `` `\pi_j` `` or `` `c_i` ``, caption-like figure/table explanations, rigid repeated evidence templates, draft leftovers such as `可复核数字包括`, and internal pipeline wording. It accepts label aliases such as `Fig. 1`, `图 1`, `Equation (3)`, and compact ranges such as `Table 4-6` when the range genuinely covers all listed items.

Treat `math_format`, `formula_depth`, and `evidence_narrative` failed gates as unfinished states in controlled final output. `math_format` usually routes to targeted patching; `formula_depth` and `evidence_narrative` usually require rewriting the affected `## 五、图表公式解释` entries from the source pack and evidence manifest.

Do not use quality status alone to decide asset correctness. Asset placement and hash identity belong to `validate_note.py --strict-evidence` plus a copy map from `prepare_output.py --sync-from-manifest --copy-map`. When no copy map exists, strict evidence validation can reveal that the batch process skipped deterministic asset copying, but those failures should be routed to the asset/evidence gate rather than treated as content-depth calibration.

For domain consistency review, write a separate domain report when the paper direction is identifiable or agent-skill-specific:

```powershell
python scripts/validate_domain_consistency.py `
  --source-pack "<source-pack.json>" `
  --precheck `
  --json > "<domain-precheck-report.json>"

python scripts/validate_domain_consistency.py `
  --note "<note-path>" `
  --source-pack "<source-pack.json>" `
  --json > "<domain-report.json>"
```

Treat non-`pass` domain status as unfinished for final delivery unless the mismatch is explicitly accepted and reported. In batch mode, `scripts/batch_note_pipeline.py` runs the `domain` stage by default; use `--fail-on-domain-gate` when non-pass domain reports should stop the run immediately instead of being recorded for later repair.

The domain report is calibrated as a paper-type and domain-positioning gate. For agent-skill papers it checks the skill object, lifecycle stage, evidence mapping, boundary discussion, and explicit paper-type alignment between the source title/abstract and the note's `论文类型` field. Optional checks such as security and framework dependency are applied only when the note/source makes them relevant. A source/note paper-type mismatch, such as treating a benchmark paper as a survey, is `needs_regeneration` because it changes the whole reading frame.

The precheck report should include `paper_type_candidate`, `paper_type_confidence`, `confidence`, `evidence.title_cues`, `evidence.abstract_cues`, optional `evidence.negative_cues`, and `draft_instruction`. Use it before drafting; use the full domain report after drafting.

Then write a separate asset report:

```powershell
python scripts/audit_note_assets.py "<note-path>" `
  --output "<asset-report.json>" `
  --scan-sibling-notes
```

For controlled final output, rerun the asset report with `--delete-duplicate-unused --fail-on-duplicates` when cleanup is allowed. The acceptable state is one physical file per image SHA256 in the note-local `assets/` folder; multiple evidence entries may share the same copy-map `markdown` path when they refer to the same underlying MinerU image bytes.

When MinerU source assets are available, also compare the source asset pool with the final note asset folder:

```powershell
python scripts/audit_unmatched_assets.py `
  --content-list "<content_list.json>" `
  --source-assets-dir "<mineru-assets-dir>" `
  --note-assets-dir "<note-assets-dir>" `
  --evidence-manifest "<working-evidence-manifest.json>" `
  --output "<unmatched-asset-report.json>" `
  --fail-on-problem-assets
```

This report is stricter than `audit_note_assets.py`: it looks for source-side formula orphan crops, structured figure/table panels, or manifest-matched assets that disappeared before final delivery. `formula_orphan_missing`, `structured_figure_or_panel_missing`, `structured_formula_missing`, and `manifest_matched_missing_from_final` are unfinished states unless explicitly reviewed and accepted.

When any gate fails, build a compact one-paper repair context:

```powershell
python scripts/build_repair_context.py `
  --paper-key "<paper-key>" `
  --source-pack "<source-pack.json>" `
  --evidence-manifest "<manifest.json>" `
  --copy-map "<copy-map.json>" `
  --note "<note-path>" `
  --quality-report "<quality-report.json>" `
  --domain-report "<domain-report.json>" `
  --validation-report "<validation-report.json>" `
  --asset-report "<asset-report.json>" `
  --output "<repair-context.json>"
```

The repair context belongs to one paper only. Do not merge body text or evidence manifests across papers.

The asset report, validation report, evidence manifest, copy map, and stage status belong in the per-paper sidecar JSON when batch generation is used:

```powershell
python scripts/update_pipeline_sidecar.py `
  --sidecar "<sidecar.json>" `
  --manifest-path "<working-evidence-manifest.json>" `
  --copy-map-path "<copy-map.json>" `
  --asset-report-path "<asset-report.json>" `
  --validation-report-path "<validation-report.json>" `
  --quality-report-path "<quality-report.json>" `
  --domain-report-path "<domain-report.json>" `
  --stage validate --status complete
```

## Skill Maintenance Smoke Test

After modifying scripts or evidence/asset rules, run:

```powershell
python scripts/smoke_test_skill.py
python -m py_compile scripts/*.py
git diff --check
```

Expected behavior:

- `smoke_test_skill.py` passes.
- `py_compile` has no syntax errors.
- No Git conflict markers remain in skill Markdown, YAML, JSON, or Python files.
- `git diff --check` has no whitespace errors. LF/CRLF warnings from Git on Windows are acceptable.

The upstream `skill-creator` `quick_validate.py` requires the Python `yaml` module. If it fails with `ModuleNotFoundError: No module named 'yaml'`, install `PyYAML` in the validation environment or report the dependency gap instead of treating it as a skill content failure.
