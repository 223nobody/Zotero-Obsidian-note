# Asset Binding

Use this file when copying, validating, or repairing images, tables, formula crops, and multi-panel figures.

## Source Of Truth

- `content_list.json` gives source order, block type, page hints, and parser asset paths.
- `evidence_manifest.json` maps paper evidence items to candidate source assets.
- `copy_map.json` is authoritative for final note-local `assets/...` links.
- Final notes must not link to absolute paths, MinerU cache paths, or raw parser paths.

## Binding States

- `matched_high_confidence`: source label and asset are strongly bound.
- `matched_medium_confidence`: source label and asset are plausible but need source-text check.
- `orphan_formula_candidate`: formula-looking crop inferred from the source asset pool; needs visual verification.
- `multi_panel_partial`: only part of a structured Figure/Table panel group is present.
- `unmatched_non_evidence`: parser asset is not a final paper evidence item.
- `unresolved_asset_binding`: the note must report this externally and cannot silently pretend the binding is certain.

## SHA256 Dedupe

When multiple source assets have identical SHA256 bytes, keep one physical note-local file and preserve all evidence bindings in the copy map. Multiple manifest items may share the same `markdown` path.

## Formula Crops

Equation/Loss/Objective blocks without direct `img_path` are still first-class evidence. If formula-looking orphan crops exist, use `audit_unmatched_assets.py` and visual verification before final delivery.

## Multi-Panel Evidence

If a figure is split into multiple panels or local crops, place all semantically linked panels under the same evidence entry. Explain each panel's role. A single representative panel is insufficient for a core multi-panel item.

## Validation

Use:

```powershell
python scripts/prepare_output.py --sync-from-manifest "<manifest.json>" --copy-map "<copy-map.json>"
python scripts/validate_note.py "<note.md>" --evidence-manifest "<manifest.json>" --copy-map "<copy-map.json>" --strict-evidence --copy-map-authoritative --json
python scripts/audit_note_assets.py "<note.md>" --output "<asset-report.json>" --delete-duplicate-unused --fail-on-duplicates
python scripts/audit_unmatched_assets.py --content-list "<content_list.json>" --source-assets-dir "<source-assets>" --note-assets-dir "<note-assets>" --evidence-manifest "<manifest.json>" --fail-on-problem-assets
```
