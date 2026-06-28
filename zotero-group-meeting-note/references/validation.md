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
8. `domain consistency gate`: paper type and domain-specific emphasis are correct.
9. `final delivery gate`: reports and sidecar status distinguish generated files from passed final notes.

Batch completion means all gates pass for that paper. A failed quality or evidence gate must trigger repair or remain in the unresolved list.

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

Then write a separate asset report:

```powershell
python scripts/audit_note_assets.py "<note-path>" `
  --output "<asset-report.json>" `
  --scan-sibling-notes
```

The asset report, validation report, evidence manifest, copy map, and stage status belong in the per-paper sidecar JSON when batch generation is used:

```powershell
python scripts/update_pipeline_sidecar.py `
  --sidecar "<sidecar.json>" `
  --manifest-path "<working-evidence-manifest.json>" `
  --copy-map-path "<copy-map.json>" `
  --asset-report-path "<asset-report.json>" `
  --validation-report-path "<validation-report.json>" `
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
