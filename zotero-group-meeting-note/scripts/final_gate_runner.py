#!/usr/bin/env python3
"""Run the final per-paper gate stack and optionally update a sidecar."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import gate_common


SCRIPT_DIR = Path(__file__).resolve().parent
VALIDATE_NOTE = SCRIPT_DIR / "validate_note.py"
AUDIT_QUALITY = SCRIPT_DIR / "audit_note_quality.py"
VALIDATE_DOMAIN = SCRIPT_DIR / "validate_domain_consistency.py"
AUDIT_ASSETS = SCRIPT_DIR / "audit_note_assets.py"
AUDIT_UNMATCHED_ASSETS = SCRIPT_DIR / "audit_unmatched_assets.py"
UPDATE_SIDECAR = SCRIPT_DIR / "update_pipeline_sidecar.py"
DEFAULT_BLUEPRINT = SCRIPT_DIR.parent / "references" / "blueprint.md"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run validation, quality, domain, asset, unmatched-asset, and final-delivery gates for one paper."
    )
    parser.add_argument("--paper-key", help="Stable paper key used for report filenames.")
    parser.add_argument("--note", required=True, help="Final Markdown note path.")
    parser.add_argument("--source-pack", help="source_pack.json path.")
    parser.add_argument("--evidence-manifest", help="Evidence manifest JSON path.")
    parser.add_argument("--copy-map", help="prepare_output.py copy-map JSON path.")
    parser.add_argument("--content-list", help="MinerU content_list.json path for unmatched-asset audit.")
    parser.add_argument("--source-assets-dir", help="MinerU source assets directory.")
    parser.add_argument("--note-assets-dir", help="Final note assets directory. Defaults to <note parent>/assets.")
    parser.add_argument("--blueprint", default=str(DEFAULT_BLUEPRINT), help="Blueprint reference path.")
    parser.add_argument("--reports-dir", help="Directory for generated JSON gate reports.")
    parser.add_argument("--output", help="Write final gate summary JSON to this path.")
    parser.add_argument("--sidecar", help="Optional per-paper sidecar JSON to update.")
    parser.add_argument("--strict-evidence", action="store_true", help="Fail validation on evidence warnings.")
    parser.add_argument(
        "--copy-map-authoritative",
        action="store_true",
        help="Require final evidence links to be backed by the copy map when present.",
    )
    parser.add_argument("--scan-sibling-notes", action="store_true", help="Asset audit scans sibling notes.")
    parser.add_argument(
        "--delete-duplicate-unused",
        action="store_true",
        help="Delete unused duplicate asset files before final asset status is decided.",
    )
    parser.add_argument("--fail-on-duplicate-assets", action="store_true")
    parser.add_argument("--fail-on-unused-assets", action="store_true")
    parser.add_argument("--fail-on-unmatched-assets", action="store_true")
    parser.add_argument(
        "--require-unmatched-assets",
        action="store_true",
        help="Fail final delivery if source assets are not available for unmatched-asset audit.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON only.")
    return parser.parse_args()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned[:80] or "paper"


def read_json(path: Path) -> Any:
    return gate_common.read_json(path)


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, encoding="utf-8", errors="replace")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    gate_common.write_json(path, payload)


def apply_command_failure(
    report: dict[str, Any],
    result: subprocess.CompletedProcess[str],
    fallback_status: str,
) -> dict[str, Any]:
    if result.returncode == 0:
        return report
    status = str(report.get("status", "") or "")
    if status not in gate_common.NON_BLOCKING_STATUSES:
        return report
    failed_gates = report.get("failed_gates", [])
    if not isinstance(failed_gates, list):
        failed_gates = [str(failed_gates)] if failed_gates else []
    if "command_failed" not in failed_gates:
        failed_gates.append("command_failed")
    report["failed_gates"] = failed_gates
    report["status"] = fallback_status if fallback_status not in gate_common.NON_BLOCKING_STATUSES else "fail"
    report["ok"] = False
    report["command_returncode"] = result.returncode
    if result.stderr:
        report["stderr"] = result.stderr
    try:
        current_problem_count = int(report.get("problem_count", 0) or 0)
    except (TypeError, ValueError):
        current_problem_count = 0
    report["problem_count"] = max(current_problem_count, len(failed_gates), 1)
    return report


def report_from_stdout(
    result: subprocess.CompletedProcess[str],
    fallback_status: str,
    report_type: str,
    input_paths: dict[str, str | Path | None],
) -> dict[str, Any]:
    try:
        report = json.loads(result.stdout or "{}")
        if isinstance(report, dict):
            normalized = gate_common.normalize_report(
                report,
                report_type=report_type,
                fallback_status=fallback_status,
            )
            normalized = apply_command_failure(normalized, result, fallback_status)
            return gate_common.attach_input_hashes(normalized, input_paths)
    except json.JSONDecodeError:
        pass
    report = {
        "schema_version": 2,
        "report_type": report_type,
        "status": fallback_status,
        "ok": False,
        "failed_gates": ["invalid_gate_output"],
        "problem_count": 1,
        "command_returncode": result.returncode,
        "stderr": result.stderr,
    }
    return gate_common.attach_input_hashes(report, input_paths)


def run_stdout_report(
    command: list[str],
    report_path: Path,
    fallback_status: str,
    report_type: str,
    input_paths: dict[str, str | Path | None],
) -> tuple[bool, dict[str, Any]]:
    result = run(command)
    report = report_from_stdout(result, fallback_status, report_type, input_paths)
    write_json(report_path, report)
    return result.returncode == 0 and report.get("status") == "pass", report


def run_file_report(
    command: list[str],
    report_path: Path,
    report_type: str,
    input_paths: dict[str, str | Path | None],
) -> tuple[bool, dict[str, Any]]:
    result = run(command)
    try:
        report = read_json(report_path)
        if isinstance(report, dict):
            report = gate_common.normalize_report(
                report,
                report_type=report_type,
                fallback_status="fail",
            )
        else:
            report = gate_common.normalize_report(
                {"failed_gates": ["invalid_gate_output"]},
                report_type=report_type,
                fallback_status="fail",
            )
    except Exception as exc:  # noqa: BLE001 - final gate summary should capture malformed reports.
        report = gate_common.normalize_report(
            {"failed_gates": ["invalid_gate_output"], "error": str(exc)},
            report_type=report_type,
            fallback_status="fail",
        )
    report = gate_common.attach_input_hashes(report, input_paths)
    report = apply_command_failure(report, result, "fail")
    write_json(report_path, report)
    return result.returncode == 0 and report.get("status") == "pass", report


def report_brief(name: str, path: Path, report: dict[str, Any]) -> dict[str, Any]:
    return gate_common.report_brief(path, report)


def failed_gate_list(reports: dict[str, dict[str, Any]]) -> list[str]:
    return gate_common.failed_gate_list(reports)


def next_action(reports: dict[str, dict[str, Any]]) -> str:
    return gate_common.next_action_for_failed_gates(failed_gate_list(reports))


def update_sidecar(
    sidecar: str,
    *,
    stage: str,
    status: str,
    message: str,
    paths: dict[str, str] | None = None,
    sets: dict[str, Any] | None = None,
) -> None:
    command = [
        sys.executable,
        str(UPDATE_SIDECAR),
        "--sidecar",
        sidecar,
        "--stage",
        stage,
        "--status",
        "complete" if status == "pass" else "failed",
        "--message",
        message,
    ]
    for key, value in (paths or {}).items():
        if value:
            option = "--" + key.replace("_", "-")
            command.extend([option, value])
    for key, value in (sets or {}).items():
        command.extend(["--set", f"{key}={json.dumps(value, ensure_ascii=False)}"])
    result = run(command)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "sidecar update failed")


def main() -> int:
    args = parse_args()
    note = Path(args.note).expanduser().resolve()
    if not note.is_file():
        raise SystemExit(f"Note not found: {note}")
    key = slug(args.paper_key or note.stem)
    reports_dir = Path(args.reports_dir).expanduser().resolve() if args.reports_dir else note.parent / "_gate_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    note_assets_dir = (
        Path(args.note_assets_dir).expanduser().resolve()
        if args.note_assets_dir
        else (note.parent / "assets").resolve()
    )
    source_pack_paths = gate_common.infer_source_pack_paths(args.source_pack)
    content_list_text = (
        gate_common.resolve_pack_path(args.content_list)
        if args.content_list
        else source_pack_paths.get("content_list", "")
    )
    source_assets_dir_text = (
        gate_common.resolve_pack_path(args.source_assets_dir)
        if args.source_assets_dir
        else source_pack_paths.get("source_assets_dir", "")
    )
    require_unmatched_assets = args.require_unmatched_assets or bool(args.source_pack)

    report_paths = {
        "validation": reports_dir / f"{key}.validation.json",
        "quality": reports_dir / f"{key}.quality.json",
        "domain": reports_dir / f"{key}.domain.json",
        "asset": reports_dir / f"{key}.asset.json",
        "unmatched_asset": reports_dir / f"{key}.unmatched-asset.json",
    }

    validation_command = [sys.executable, str(VALIDATE_NOTE), str(note), "--json"]
    if args.evidence_manifest:
        validation_command.extend(["--evidence-manifest", str(Path(args.evidence_manifest).expanduser().resolve())])
    if args.copy_map:
        validation_command.extend(["--copy-map", str(Path(args.copy_map).expanduser().resolve())])
    if args.blueprint:
        validation_command.extend(["--blueprint", str(Path(args.blueprint).expanduser().resolve())])
    if args.strict_evidence:
        validation_command.append("--strict-evidence")
    if args.copy_map_authoritative:
        validation_command.append("--copy-map-authoritative")
    _, validation_report = run_stdout_report(
        validation_command,
        report_paths["validation"],
        "fail",
        "validation",
        {
            "note": note,
            "evidence_manifest": args.evidence_manifest,
            "copy_map": args.copy_map,
            "blueprint": args.blueprint,
        },
    )

    quality_command = [sys.executable, str(AUDIT_QUALITY), "--note", str(note), "--json"]
    if args.source_pack:
        quality_command.extend(["--source-pack", str(Path(args.source_pack).expanduser().resolve())])
    if args.evidence_manifest:
        quality_command.extend(["--evidence-manifest", str(Path(args.evidence_manifest).expanduser().resolve())])
    if args.blueprint:
        quality_command.extend(["--blueprint", str(Path(args.blueprint).expanduser().resolve())])
    _, quality_report = run_stdout_report(
        quality_command,
        report_paths["quality"],
        "needs_major_repair",
        "quality",
        {
            "note": note,
            "source_pack": args.source_pack,
            "evidence_manifest": args.evidence_manifest,
            "blueprint": args.blueprint,
        },
    )

    domain_command = [sys.executable, str(VALIDATE_DOMAIN), "--note", str(note), "--json"]
    if args.source_pack:
        domain_command.extend(["--source-pack", str(Path(args.source_pack).expanduser().resolve())])
    _, domain_report = run_stdout_report(
        domain_command,
        report_paths["domain"],
        "needs_major_repair",
        "domain",
        {
            "note": note,
            "source_pack": args.source_pack,
        },
    )

    asset_command = [
        sys.executable,
        str(AUDIT_ASSETS),
        str(note),
        "--assets-dir",
        str(note_assets_dir),
        "--output",
        str(report_paths["asset"]),
    ]
    if args.scan_sibling_notes:
        asset_command.append("--scan-sibling-notes")
    if args.delete_duplicate_unused:
        asset_command.append("--delete-duplicate-unused")
    if args.fail_on_duplicate_assets:
        asset_command.append("--fail-on-duplicates")
    if args.fail_on_unused_assets:
        asset_command.append("--fail-on-unused")
    _, asset_report = run_file_report(
        asset_command,
        report_paths["asset"],
        "asset",
        {
            "note": note,
            "note_assets_dir": note_assets_dir,
        },
    )

    unmatched_report: dict[str, Any]
    if source_assets_dir_text:
        unmatched_command = [
            sys.executable,
            str(AUDIT_UNMATCHED_ASSETS),
            "--source-assets-dir",
            str(Path(source_assets_dir_text).expanduser().resolve()),
            "--note-assets-dir",
            str(note_assets_dir),
            "--output",
            str(report_paths["unmatched_asset"]),
        ]
        if content_list_text:
            unmatched_command.extend(["--content-list", str(Path(content_list_text).expanduser().resolve())])
        if args.evidence_manifest:
            unmatched_command.extend(["--evidence-manifest", str(Path(args.evidence_manifest).expanduser().resolve())])
        if args.fail_on_unmatched_assets:
            unmatched_command.append("--fail-on-problem-assets")
        _, unmatched_report = run_file_report(
            unmatched_command,
            report_paths["unmatched_asset"],
            "unmatched_asset",
            {
                "content_list": content_list_text,
                "evidence_manifest": args.evidence_manifest,
                "source_assets_dir": source_assets_dir_text,
                "note_assets_dir": note_assets_dir,
            },
        )
    else:
        unmatched_report = gate_common.normalize_report(
            {
                "failed_gates": ["missing_source_assets_dir"] if require_unmatched_assets else [],
                "message": "source assets directory missing",
            },
            report_type="unmatched_asset",
            fallback_status="fail" if require_unmatched_assets else "skipped",
        )
        gate_common.attach_input_hashes(
            unmatched_report,
            {
                "content_list": content_list_text,
                "evidence_manifest": args.evidence_manifest,
                "note_assets_dir": note_assets_dir,
            },
        )
        write_json(report_paths["unmatched_asset"], unmatched_report)

    asset_report["unmatched_asset_report"] = unmatched_report
    asset_report["unmatched_asset_report_path"] = str(report_paths["unmatched_asset"])
    write_json(report_paths["asset"], asset_report)

    reports = {
        "validation": report_brief("validation", report_paths["validation"], validation_report),
        "quality": report_brief("quality", report_paths["quality"], quality_report),
        "domain": report_brief("domain", report_paths["domain"], domain_report),
        "asset": report_brief("asset", report_paths["asset"], asset_report),
        "unmatched_asset": report_brief(
            "unmatched_asset", report_paths["unmatched_asset"], unmatched_report
        ),
    }
    failed_gates = failed_gate_list(reports)
    status = "pass" if not failed_gates else "fail"
    summary = {
        "schema_version": 2,
        "report_type": "final_gate",
        "paper_key": key,
        "note": str(note),
        "status": status,
        "ok": status == "pass",
        "created_at": now_iso(),
        "reports": reports,
        "failed_gates": failed_gates,
        "next_action": next_action(reports),
    }
    gate_common.attach_input_hashes(
        summary,
        {
            "note": note,
            "source_pack": args.source_pack,
            "evidence_manifest": args.evidence_manifest,
            "copy_map": args.copy_map,
            "content_list": content_list_text,
            "source_assets_dir": source_assets_dir_text,
            "note_assets_dir": note_assets_dir,
        },
    )
    output_path = Path(args.output).expanduser().resolve() if args.output else reports_dir / f"{key}.final-gate.json"
    write_json(output_path, summary)

    if args.sidecar:
        sidecar_paths = {
            "note_path": str(note),
            "validation_report_path": str(report_paths["validation"]),
            "quality_report_path": str(report_paths["quality"]),
            "domain_report_path": str(report_paths["domain"]),
            "asset_report_path": str(report_paths["asset"]),
        }
        if args.evidence_manifest:
            sidecar_paths["manifest_path"] = str(Path(args.evidence_manifest).expanduser().resolve())
        if args.copy_map:
            sidecar_paths["copy_map_path"] = str(Path(args.copy_map).expanduser().resolve())
        update_sidecar(args.sidecar, stage="validate", status=reports["validation"]["status"], message="final gate validation", paths=sidecar_paths)
        update_sidecar(args.sidecar, stage="quality", status=reports["quality"]["status"], message="final gate quality")
        update_sidecar(args.sidecar, stage="domain", status=reports["domain"]["status"], message="final gate domain")
        update_sidecar(args.sidecar, stage="cleanup_report", status=reports["asset"]["status"], message="final gate asset")
        update_sidecar(
            args.sidecar,
            stage="final_delivery",
            status=status,
            message="final delivery gates passed" if status == "pass" else "final delivery gates failed",
            sets={
                "paths.unmatched_asset_report_path": str(report_paths["unmatched_asset"]),
                "final_status": status,
                "final_gate_report_path": str(output_path),
                "gates.final.failed_gates": failed_gates,
                "gates.final.next_action": summary["next_action"],
            },
        )

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"Final gate status: {status}")
        print(f"Report: {output_path}")
        if failed_gates:
            print("Failed gates: " + ", ".join(failed_gates))
            print(f"Next action: {summary['next_action']}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
