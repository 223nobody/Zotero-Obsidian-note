#!/usr/bin/env python3
"""Validate and optionally migrate a per-paper batch sidecar."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import gate_common


STAGES = [
    "preflight",
    "parse_cache",
    "evidence_manifest",
    "domain_precheck",
    "draft",
    "review",
    "quality",
    "domain",
    "validate",
    "repair",
    "cleanup_report",
    "final_delivery",
]

PATH_KEYS = [
    "pdf_path",
    "source_md",
    "content_list",
    "assets_dir",
    "note_path",
    "manifest_path",
    "copy_map_path",
    "asset_report_path",
    "unmatched_asset_report_path",
    "validation_report_path",
    "quality_report_path",
    "domain_report_path",
]

REPORT_PATH_KEYS = {
    "validation_report_path": "validation",
    "quality_report_path": "quality",
    "domain_report_path": "domain",
    "asset_report_path": "asset",
    "unmatched_asset_report_path": "unmatched_asset",
}

VALID_STAGE_STATUS = {"pending", "running", "complete", "failed", "skipped"}
PASS_STATUSES = {"pass"}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate sidecar schema, report paths, and final-delivery gate consistency."
    )
    parser.add_argument("sidecar", help="Sidecar JSON path.")
    parser.add_argument(
        "--write-migrated",
        action="store_true",
        help="Write schema v2 defaults back to the sidecar after validation.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown.")
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return gate_common.read_json(path)


def file_sha256(path: Path) -> str:
    return gate_common.file_sha256(path)


def normalize_sidecar(sidecar: dict[str, Any]) -> dict[str, Any]:
    sidecar["schema_version"] = max(int(sidecar.get("schema_version", 1) or 1), 2)
    sidecar.setdefault("created_at", now_iso())
    sidecar.setdefault("updated_at", now_iso())
    sidecar.setdefault("paper_key", "")
    sidecar.setdefault("title", "")
    paths = sidecar.setdefault("paths", {})
    for key in PATH_KEYS:
        paths.setdefault(key, "")
    stages = sidecar.setdefault("stages", {})
    for stage in STAGES:
        stages.setdefault(stage, {"status": "pending", "updated_at": "", "message": ""})
    sidecar.setdefault("reports", {})
    sidecar.setdefault("gates", {})
    sidecar.setdefault("counts", {})
    sidecar.setdefault("source_pack_quality", {})
    sidecar.setdefault("artifact_hashes", {})
    sidecar.setdefault("validation", {})
    sidecar.setdefault("quality", {})
    sidecar.setdefault("domain", {})
    sidecar.setdefault("asset", {})
    sidecar.setdefault("asset_unmatched", {})
    sidecar.setdefault("errors", [])
    return sidecar


def report_status(path_text: str) -> tuple[str, dict[str, Any]]:
    return gate_common.report_status(path_text)


def normalized_path(path_text: str) -> str:
    if not path_text:
        return ""
    return str(Path(path_text).expanduser().resolve())


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def validate(sidecar_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    sidecar = normalize_sidecar(read_json(sidecar_path))
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    paths = sidecar.get("paths", {})
    stages = sidecar.get("stages", {})

    for stage, payload in stages.items():
        if stage not in STAGES:
            warnings.append({"kind": "unknown_stage", "stage": stage})
            continue
        if not isinstance(payload, dict):
            errors.append({"kind": "invalid_stage_payload", "stage": stage})
            continue
        status = str(payload.get("status", ""))
        if status not in VALID_STAGE_STATUS:
            errors.append({"kind": "invalid_stage_status", "stage": stage, "status": status})

    for stage in STAGES:
        if stage not in stages:
            errors.append({"kind": "missing_stage", "stage": stage})

    path_statuses: dict[str, str] = {}
    artifact_hashes: dict[str, str] = {}
    for key, value in paths.items():
        if not value:
            path_statuses[key] = "empty"
            continue
        path = Path(str(value)).expanduser().resolve()
        if path.is_file():
            path_statuses[key] = "file"
            artifact_hashes[key] = file_sha256(path)
        elif path.is_dir():
            path_statuses[key] = "dir"
        else:
            path_statuses[key] = "missing"
            if key in REPORT_PATH_KEYS or key in {"note_path", "manifest_path", "copy_map_path"}:
                errors.append({"kind": "missing_path", "path_key": key, "path": str(path)})

    report_statuses: dict[str, str] = {}
    report_staleness: list[dict[str, Any]] = []
    failed_gates: list[str] = []
    for path_key, gate_name in REPORT_PATH_KEYS.items():
        status, report = report_status(str(paths.get(path_key, "")))
        if not status:
            continue
        report_statuses[gate_name] = status
        for gate in report.get("failed_gates", []) if isinstance(report, dict) else []:
            failed_gates.append(f"{gate_name}/{gate}")
        if status not in PASS_STATUSES:
            failed_gates.append(f"{gate_name}/{status}")
        for stale in gate_common.stale_input_hashes(report):
            stale_record = dict(stale)
            stale_record["gate"] = gate_name
            report_staleness.append(stale_record)
            errors.append(
                {
                    "kind": "stale_gate_report",
                    "gate": gate_name,
                    "input": stale.get("input", ""),
                    "path": stale.get("path", ""),
                }
            )

    final_stage = stages.get("final_delivery", {})
    final_status = str(final_stage.get("status", "")) if isinstance(final_stage, dict) else ""
    if final_status == "complete":
        if sidecar.get("final_status") != "pass":
            errors.append(
                {
                    "kind": "final_delivery_status_mismatch",
                    "final_status": sidecar.get("final_status", ""),
                }
            )
        required_reports = ["validation", "quality", "domain", "asset"]
        for gate_name in required_reports:
            status = report_statuses.get(gate_name, "")
            if status != "pass":
                errors.append(
                    {
                        "kind": "final_delivery_without_pass_report",
                        "gate": gate_name,
                        "status": status or "missing",
                    }
                )
        unmatched_status = report_statuses.get("unmatched_asset", "")
        source_assets_available = bool(str(paths.get("assets_dir", "")).strip())
        if source_assets_available and unmatched_status != "pass":
            errors.append(
                {
                    "kind": "final_delivery_without_pass_report",
                    "gate": "unmatched_asset",
                    "status": unmatched_status or "missing",
                }
            )
        elif unmatched_status and unmatched_status not in {"pass", "skipped"}:
            errors.append(
                {
                    "kind": "final_delivery_without_pass_report",
                    "gate": "unmatched_asset",
                    "status": unmatched_status,
                }
            )
        final_gate_path = str(sidecar.get("final_gate_report_path") or "")
        if not final_gate_path:
            errors.append({"kind": "missing_final_gate_report_path"})
        else:
            final_gate_status, final_gate_report = report_status(final_gate_path)
            if final_gate_status != "pass":
                errors.append(
                    {
                        "kind": "final_gate_report_not_pass",
                        "status": final_gate_status or "missing",
                        "path": str(Path(final_gate_path).expanduser().resolve()),
                    }
                )
            if isinstance(final_gate_report, dict):
                for stale in gate_common.stale_input_hashes(final_gate_report):
                    stale_record = dict(stale)
                    stale_record["gate"] = "final_gate"
                    report_staleness.append(stale_record)
                    errors.append(
                        {
                            "kind": "stale_gate_report",
                            "gate": "final_gate",
                            "input": stale.get("input", ""),
                            "path": stale.get("path", ""),
                        }
                    )
                if final_gate_report.get("status") != sidecar.get("final_status"):
                    errors.append(
                        {
                            "kind": "final_status_not_equal_final_gate_report",
                            "sidecar_final_status": sidecar.get("final_status", ""),
                            "final_gate_status": final_gate_report.get("status", ""),
                        }
                    )
                sidecar_note = normalized_path(str(paths.get("note_path") or ""))
                final_gate_note = normalized_path(
                    str(
                        final_gate_report.get("note")
                        or final_gate_report.get("input_paths", {}).get("note")
                        or ""
                    )
                )
                if sidecar_note and final_gate_note and sidecar_note != final_gate_note:
                    errors.append(
                        {
                            "kind": "final_gate_note_mismatch",
                            "sidecar_note": sidecar_note,
                            "final_gate_note": final_gate_note,
                        }
                    )
                sidecar_paper_key = str(sidecar.get("paper_key") or "")
                final_gate_paper_key = str(final_gate_report.get("paper_key") or "")
                if sidecar_paper_key and final_gate_paper_key and sidecar_paper_key != final_gate_paper_key:
                    errors.append(
                        {
                            "kind": "final_gate_paper_key_mismatch",
                            "sidecar_paper_key": sidecar_paper_key,
                            "final_gate_paper_key": final_gate_paper_key,
                        }
                    )
                report_summaries = final_gate_report.get("reports", {})
                if isinstance(report_summaries, dict):
                    for path_key, gate_name in REPORT_PATH_KEYS.items():
                        expected = normalized_path(str(paths.get(path_key) or ""))
                        actual = ""
                        gate_summary = report_summaries.get(gate_name)
                        if isinstance(gate_summary, dict):
                            actual = normalized_path(str(gate_summary.get("path") or ""))
                        if expected and actual and expected != actual:
                            errors.append(
                                {
                                    "kind": "final_gate_report_path_mismatch",
                                    "gate": gate_name,
                                    "sidecar_report_path": expected,
                                    "final_gate_report_path": actual,
                                }
                            )
    repair = sidecar.get("repair", {}) if isinstance(sidecar.get("repair"), dict) else {}
    rounds_completed = safe_int(repair.get("rounds_completed", 0), 0)
    if rounds_completed > 2:
        errors.append(
            {
                "kind": "repair_rounds_exceeded",
                "rounds_completed": rounds_completed,
                "maximum": 2,
            }
        )

    result = {
        "schema_version": 2,
        "report_type": "sidecar_validation",
        "sidecar": str(sidecar_path),
        "status": "fail" if errors else "pass",
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "failed_gates": sorted(set(failed_gates)),
        "problem_count": len(errors),
        "summary": {
            "paper_key": sidecar.get("paper_key", ""),
            "title": sidecar.get("title", ""),
            "stage_count": len(stages),
            "path_statuses": path_statuses,
            "report_statuses": report_statuses,
            "report_staleness": report_staleness,
            "artifact_hashes": artifact_hashes,
            "repair_rounds_completed": rounds_completed,
        },
    }
    sidecar.setdefault("artifact_hashes", {}).update(artifact_hashes)
    return result, sidecar


def markdown_report(result: dict[str, Any]) -> str:
    lines = [
        "# Sidecar Validation",
        "",
        f"Sidecar: {result['sidecar']}",
        f"Status: {result['status']}",
        "",
        "## Failed Gates",
    ]
    failed_gates = result.get("failed_gates", [])
    lines.extend([f"- {gate}" for gate in failed_gates] if failed_gates else ["- <none>"])
    lines.extend(["", "## Errors"])
    errors = result.get("errors", [])
    lines.extend([f"- {item}" for item in errors] if errors else ["- <none>"])
    lines.extend(["", "## Warnings"])
    warnings = result.get("warnings", [])
    lines.extend([f"- {item}" for item in warnings] if warnings else ["- <none>"])
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    sidecar_path = Path(args.sidecar).expanduser().resolve()
    if not sidecar_path.is_file():
        raise SystemExit(f"Sidecar not found: {sidecar_path}")
    result, migrated = validate(sidecar_path)
    if args.write_migrated:
        sidecar_path.write_text(json.dumps(migrated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(markdown_report(result), end="")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
