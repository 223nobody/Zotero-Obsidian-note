# Batch Control

Use this file for `batch-final-controlled` runs.

## Batch Boundary

These steps may be batched:

- preflight and source-pack quality checks
- PDF/MinerU matching and cache normalization
- source pack construction
- evidence manifest construction
- copy-map creation and asset migration
- preliminary validation reports

These steps must stay one paper at a time:

- final-note writing
- review pass
- repair
- final validation
- final delivery decision

## Required Per-Paper Artifacts

Each paper must have:

- `source_pack.json`
- `evidence_manifest.json`
- `copy_map.json`
- `validation_report.json`
- `quality_report.json`
- `domain_report.json`
- `asset_report.json`
- `unmatched_asset_report.json` when MinerU assets are available
- `sidecar.json`
- repair instructions or unresolved report when gates fail

## Recommended Pipeline

```powershell
python scripts/batch_note_pipeline.py "<batch.json>" `
  --work-dir "<work-dir>" `
  --stages preflight,parse_cache,evidence_manifest,domain_precheck `
  --production-mode batch-final-controlled `
  --continue-on-error
```

After each paper's note is written:

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

The runner is the preferred one-paper final gate entrypoint. It does not draft or repair prose. It only runs the required final reports, emits `<paper-key>.final-gate.json`, writes report paths back to the sidecar when `--sidecar` is supplied, and marks `final_delivery` complete only when every required report is pass.
The runner records `input_hashes` in its reports. After any note, source-pack, manifest, copy-map, content-list, or blueprint change, rerun the runner rather than reusing old reports. For MinerU-backed papers, source assets should be passed directly or inferable from `source_pack.json`; otherwise the unmatched-asset gate is unfinished.
The runner also treats any nonzero child command return code as a failed gate, even when the child report body claims `status=pass`.
The runner records file and directory input fingerprints. Note-local assets and MinerU source assets are stale inputs: if files are deleted, added, or modified, rerun the final gate runner.

Equivalent batch-stage validation is:

```powershell
python scripts/batch_note_pipeline.py "<single-or-batch.json>" `
  --work-dir "<work-dir>" `
  --stages quality,domain,validate,repair,cleanup_report,final_delivery `
  --production-mode batch-final-controlled `
  --fail-on-quality-gate `
  --fail-on-domain-gate `
  --strict-evidence `
  --copy-map-authoritative `
  --repair-rounds 2 `
  --continue-on-error `
  --final-report "<batch-final-summary.md>"
```

In this mode, the `final_delivery` stage calls `scripts/final_gate_runner.py` once per paper and relies on its `final-gate.json`; it must not complete from old report paths alone.

## Sidecar Rules

- Store paths, report statuses, failed gates, failed items, repair history, source-pack quality, and artifact hashes in the sidecar.
- Do not treat stale reports as current after the note, source pack, evidence manifest, or copy map changes.
- `final_delivery=pass` requires validation, quality, domain, asset, and unmatched-asset gates to pass.
- Use `scripts/validate_sidecar.py "<sidecar.json>" --write-migrated --json` to migrate older sidecars to schema v2 and verify that final-delivery status is consistent with gate reports, same-paper/same-note final-gate report status, repair-round limits, report input hashes, and asset-directory fingerprints.

## Batch Report Rules

The batch report must include:

- batch health totals
- failed gate clusters
- next repair queue
- per-paper note/source-pack path
- per-paper status and unresolved issue

Only papers passing every gate count as complete.
