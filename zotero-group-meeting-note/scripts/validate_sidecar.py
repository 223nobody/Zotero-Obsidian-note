#!/usr/bin/env python3
"""Validate and optionally migrate a per-paper batch sidecar."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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
PASS_STATUSES = {"pass", "warning"}

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
    return json.loads(path.read_text(encoding="utf-8-sig", errors="ignore"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    if not path_text:
        return "", {}
    path = Path(path_text).expanduser().resolve()
    if not path.is_file():
        return "missing_report", {}
    try:
        report = read_json(path)
    except Exception as exc:  # noqa: BLE001 - validator should report malformed JSON.
        return f"invalid_json:{exc}", {}
    status = str(report.get("status", "pass" if not report.get("failed_gates") else "fail") or "")
    return status, report if isinstance(report, dict) else {}


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

    final_stage = stages.get("final_delivery", {})
    final_status = str(final_stage.get("status", "")) if isinstance(final_stage, dict) else ""
    if final_status == "complete":
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
        if unmatched_status and unmatched_status != "pass":
            errors.append(
                {
                    "kind": "final_delivery_without_pass_report",
                    "gate": "unmatched_asset",
                    "status": unmatched_status,
                }
            )

    result = {
        "schema_version": 1,
        "report_type": "sidecar_validation",
        "sidecar": str(sidecar_path),
        "status": "fail" if errors else "pass",
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "failed_gates": sorted(set(failed_gates)),
        "summary": {
            "paper_key": sidecar.get("paper_key", ""),
            "title": sidecar.get("title", ""),
            "stage_count": len(stages),
            "path_statuses": path_statuses,
            "report_statuses": report_statuses,
            "artifact_hashes": artifact_hashes,
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
