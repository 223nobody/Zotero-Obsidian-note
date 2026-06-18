# Validation

Use this reference when validating generated notes or after changing skill scripts/references.

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
  --evidence-manifest "<working-evidence-manifest.json>" `
  --copy-map "<copy-map.json>" `
  --strict-evidence `
  --json > "<validation-report.json>"
```

When `--evidence-manifest` is used without `--strict-evidence`, warnings such as `missing_evidence_reference`, `missing_evidence_asset_link`, and `misplaced_evidence_asset_link` mean the note is structurally readable but does not fully satisfy evidence placement. Use `--strict-evidence` for batch delivery so those gaps fail validation.

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
