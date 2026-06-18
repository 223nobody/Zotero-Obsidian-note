#!/usr/bin/env python3
"""Run deterministic batch-note pipeline stages and maintain per-paper sidecars.

This helper does not draft prose. It prepares and validates the machine-readable
state around drafting so a Codex run can resume paper-by-paper.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
BUILD_MANIFEST = SCRIPT_DIR / "build_evidence_manifest.py"
VALIDATE_NOTE = SCRIPT_DIR / "validate_note.py"
AUDIT_ASSETS = SCRIPT_DIR / "audit_note_assets.py"
UPDATE_SIDECAR = SCRIPT_DIR / "update_pipeline_sidecar.py"

STAGES = [
    "preflight",
    "parse_cache",
    "evidence_manifest",
    "draft",
    "review",
    "validate",
    "cleanup_report",
]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run deterministic preflight/manifest/validation/asset-report stages "
            "for a batch of group-meeting notes."
        )
    )
    parser.add_argument(
        "batch_json",
        help=(
            "JSON file containing either a list of paper records or an object with a "
            "'papers' list. Each record may contain paper_key, title, pdf_path, "
            "source_md/full_md_path, content_list/content_list_path, assets_dir, and note_path."
        ),
    )
    parser.add_argument(
        "--work-dir",
        required=True,
        help="Working directory for sidecars, evidence manifests, and JSON reports.",
    )
    parser.add_argument(
        "--stages",
        default=",".join(STAGES),
        help=f"Comma-separated subset of stages to run. Available: {', '.join(STAGES)}.",
    )
    parser.add_argument(
        "--delete-duplicate-unused",
        action="store_true",
        help="When running cleanup_report, delete unused duplicate assets after reporting.",
    )
    parser.add_argument(
        "--strict-evidence",
        action="store_true",
        help="When validating with a manifest, treat evidence-placement warnings as failures.",
    )
    parser.add_argument(
        "--copy-map-authoritative",
        action="store_true",
        help="When a record has copy_map_path, validate evidence links only against that copy map.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue to the next paper after a stage failure.",
    )
    return parser.parse_args()


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig", errors="ignore"))


def load_batch(path: Path) -> list[dict[str, Any]]:
    data = read_json(path)
    papers = data.get("papers", data) if isinstance(data, dict) else data
    if not isinstance(papers, list):
        raise SystemExit("batch_json must contain a list or an object with a 'papers' list")
    return [paper for paper in papers if isinstance(paper, dict)]


def slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned[:80] or "paper"


def paper_key(record: dict[str, Any], index: int) -> str:
    for key in ("paper_key", "key", "id"):
        value = str(record.get(key, "")).strip()
        if value:
            return slug(value)
    for key in ("title", "note_path", "pdf_path"):
        value = str(record.get(key, "")).strip()
        if value:
            return slug(Path(value).stem if key.endswith("_path") else value)
    return f"paper-{index:04d}"


def first_value(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = str(record.get(key, "")).strip()
        if value:
            return value
    return ""


def manifest_items(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if "items" in manifest:
        return list(manifest.get("items", []))
    return list(manifest.get("main_items", [])) + list(manifest.get("post_reference_items", []))


def manifest_counts(path: Path | None) -> dict[str, int]:
    if not path or not path.is_file():
        return {}
    manifest = read_json(path)
    items = manifest_items(manifest)
    return {
        "evidence_total": len(items),
        "evidence_matched_assets": sum(1 for item in items if item.get("asset_paths")),
        "evidence_missing_assets": sum(1 for item in items if not item.get("asset_paths")),
        "evidence_high_confidence": sum(1 for item in items if item.get("match_confidence") == "high"),
        "supplementary_items": sum(
            1 for item in items if item.get("region") in {"appendix", "post_reference"}
        ),
        "post_reference_items": sum(1 for item in items if item.get("region") == "post_reference"),
        "appendix_items": sum(1 for item in items if item.get("region") == "appendix"),
    }


def validation_counts(report_path: Path | None) -> dict[str, int]:
    if not report_path or not report_path.is_file():
        return {}
    report = read_json(report_path)
    counts = {
        "validation_error_count": len(report.get("errors", [])),
        "validation_warning_count": len(report.get("warnings", [])),
        "validation_image_count": int(report.get("image_count", 0) or 0),
    }
    qa_path = report_path.with_suffix(".qa.json")
    if qa_path.is_file():
        qa_report = read_json(qa_path)
        counts.update(
            {
                "qa_total_items": int(qa_report.get("total_items", 0) or 0),
                "qa_matched_count": int(qa_report.get("matched_count", 0) or 0),
                "qa_problem_count": int(qa_report.get("problem_count", 0) or 0),
            }
        )
    return counts


def validation_sidecar_fields(report_path: Path | None) -> dict[str, Any]:
    if not report_path or not report_path.is_file():
        return {}
    report = read_json(report_path)
    payload: dict[str, Any] = {
        "validation": {
            "status": report.get("status", ""),
            "report_path": str(report_path),
            "error_count": len(report.get("errors", [])),
            "warning_count": len(report.get("warnings", [])),
        }
    }
    qa_path = report_path.with_suffix(".qa.json")
    if qa_path.is_file():
        qa_report = read_json(qa_path)
        payload["validation"]["qa_report_path"] = str(qa_path)
        payload["validation"]["qa_problem_count"] = qa_report.get("problem_count", 0)
        payload["review_items"] = [
            {
                "item_key": item.get("item_key", ""),
                "label": item.get("label", ""),
                "status": item.get("status", ""),
                "window_line": item.get("window_line", 0),
            }
            for item in qa_report.get("items", [])
            if item.get("status") != "matched"
        ]
    return payload


def asset_sidecar_fields(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "used_images": [
            {
                "path": record.get("path", ""),
                "sha256": record.get("sha256", ""),
            }
            for record in report.get("assets", [])
            if record.get("referenced")
        ],
        "unused_images": [
            {
                "path": record.get("path", ""),
                "sha256": record.get("sha256", ""),
                "referenced_by_sibling_note": record.get("referenced_by_sibling_note", False),
            }
            for record in report.get("unused_assets", [])
        ],
    }


def counts_to_set_args(counts: dict[str, int]) -> list[str]:
    args: list[str] = []
    for key, value in counts.items():
        args.extend(["--set", f"counts.{key}={value}"])
    return args


def fields_to_set_args(fields: dict[str, Any]) -> list[str]:
    args: list[str] = []
    for key, value in fields.items():
        args.extend(["--set", f"{key}={json.dumps(value, ensure_ascii=False)}"])
    return args


def update_sidecar(
    sidecar: Path,
    record: dict[str, Any],
    stage: str,
    status: str,
    message: str = "",
    extra_args: list[str] | None = None,
) -> None:
    command = [
        sys.executable,
        str(UPDATE_SIDECAR),
        "--sidecar",
        str(sidecar),
        "--stage",
        stage,
        "--status",
        status,
    ]
    if message:
        command.extend(["--message", message])

    mappings = {
        "--paper-key": first_value(record, "paper_key", "key", "id"),
        "--title": first_value(record, "title"),
        "--pdf-path": first_value(record, "pdf_path"),
        "--source-md": first_value(record, "source_md", "full_md_path", "full_md"),
        "--content-list": first_value(record, "content_list", "content_list_path"),
        "--assets-dir": first_value(record, "assets_dir"),
        "--note-path": first_value(record, "note_path", "obsidian_note_path"),
        "--manifest-path": first_value(record, "manifest_path"),
        "--copy-map-path": first_value(record, "copy_map_path"),
        "--asset-report-path": first_value(record, "asset_report_path"),
        "--validation-report-path": first_value(record, "validation_report_path"),
    }
    for flag, value in mappings.items():
        if value:
            command.extend([flag, value])
    if extra_args:
        command.extend(extra_args)
    result = run(command)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)


def preflight(record: dict[str, Any], requested_stages: list[str]) -> tuple[bool, str]:
    has_identity = any(first_value(record, key) for key in ("paper_key", "key", "id", "title"))
    has_source = any(
        first_value(record, key)
        for key in ("pdf_path", "source_md", "full_md_path", "full_md", "content_list", "content_list_path")
    )
    if not has_identity and not has_source:
        return False, "Missing minimum paper identity/source: provide paper_key/title or a source path."

    required_values: list[tuple[str, str]] = []
    if "parse_cache" in requested_stages:
        parse_artifact = first_value(record, "content_list", "content_list_path") or first_value(
            record, "source_md", "full_md_path", "full_md"
        )
        required_values.append(("parse_cache_artifact", parse_artifact))
    if "evidence_manifest" in requested_stages:
        required_values.append(("content_list", first_value(record, "content_list", "content_list_path")))
    if any(stage in requested_stages for stage in ("draft", "review", "validate", "cleanup_report")):
        required_values.append(("note_path", first_value(record, "note_path", "obsidian_note_path")))

    missing_required = [name for name, value in required_values if not value]
    if missing_required:
        return False, "Missing required fields for requested stages: " + ", ".join(missing_required)

    required_when_present = [
        ("pdf_path", first_value(record, "pdf_path")),
        ("source_md", first_value(record, "source_md", "full_md_path", "full_md")),
        ("content_list", first_value(record, "content_list", "content_list_path")),
        ("assets_dir", first_value(record, "assets_dir")),
        ("note_path", first_value(record, "note_path", "obsidian_note_path")),
    ]
    missing = [
        f"{name}={value}"
        for name, value in required_when_present
        if value and not Path(value).expanduser().exists()
    ]
    if missing:
        return False, "Missing paths: " + "; ".join(missing)
    return True, "preflight paths checked"


def run_parse_cache_checkpoint(record: dict[str, Any]) -> tuple[bool, str]:
    artifacts = [
        ("content_list", first_value(record, "content_list", "content_list_path")),
        ("source_md", first_value(record, "source_md", "full_md_path", "full_md")),
        ("assets_dir", first_value(record, "assets_dir")),
    ]
    present = [name for name, value in artifacts if value and Path(value).expanduser().exists()]
    if present:
        return True, "parse/cache artifacts present: " + ", ".join(present)
    return False, "parse/cache artifacts are missing; run paper-search-mcp parsing first"


def run_draft_checkpoint(record: dict[str, Any]) -> tuple[bool, str]:
    note = first_value(record, "note_path", "obsidian_note_path")
    if not note:
        return False, "note_path is missing; draft stage has not produced a note"
    note_path = Path(note).expanduser().resolve()
    if not note_path.is_file():
        return False, f"draft note not found: {note_path}"
    if note_path.stat().st_size == 0:
        return False, f"draft note is empty: {note_path}"
    return True, "draft note exists"


def run_review_checkpoint(record: dict[str, Any]) -> tuple[str, str]:
    review_status = first_value(record, "review_status").lower()
    if review_status in {"complete", "completed", "reviewed", "pass", "passed"}:
        return "complete", "review marked complete by batch record"
    review_report = first_value(record, "review_report_path")
    if review_report and Path(review_report).expanduser().is_file():
        return "complete", "review report exists"
    return "skipped", "manual/LLM review is not automated by batch_note_pipeline.py"


def run_manifest(record: dict[str, Any], work_dir: Path, key: str) -> tuple[bool, str, Path | None]:
    content_list = first_value(record, "content_list", "content_list_path")
    if not content_list:
        return False, "content_list path is missing", None
    content_list_path = Path(content_list).expanduser().resolve()
    if not content_list_path.is_file():
        return False, f"content_list not found: {content_list_path}", None
    manifest_path = Path(first_value(record, "manifest_path") or (work_dir / "manifests" / f"{key}.evidence.json"))
    manifest_path = manifest_path.expanduser().resolve()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(BUILD_MANIFEST),
        str(content_list_path),
        "--output",
        str(manifest_path),
        "--split-regions",
    ]
    assets_dir = first_value(record, "assets_dir")
    if assets_dir:
        command.extend(["--assets-dir", str(Path(assets_dir).expanduser().resolve())])
    full_md = first_value(record, "source_md", "full_md_path", "full_md")
    if full_md:
        command.extend(["--full-md", str(Path(full_md).expanduser().resolve())])
    result = run(command)
    if result.returncode != 0:
        return False, result.stderr or result.stdout, manifest_path
    record["manifest_path"] = str(manifest_path)
    return True, "evidence manifest built", manifest_path


def run_validation(
    record: dict[str, Any],
    work_dir: Path,
    key: str,
    strict_evidence: bool,
    copy_map_authoritative: bool,
) -> tuple[bool, str, Path | None]:
    note = first_value(record, "note_path", "obsidian_note_path")
    if not note:
        return False, "note_path is missing", None
    note_path = Path(note).expanduser().resolve()
    if not note_path.is_file():
        return False, f"note not found: {note_path}", None
    report_path = Path(
        first_value(record, "validation_report_path")
        or (work_dir / "reports" / f"{key}.validation.json")
    ).expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(VALIDATE_NOTE), str(note_path), "--json"]
    qa_report_path = report_path.with_suffix(".qa.json")
    manifest = first_value(record, "manifest_path")
    if manifest:
        command.extend(["--evidence-manifest", str(Path(manifest).expanduser().resolve())])
        command.extend(["--qa-report", str(qa_report_path)])
    copy_map = first_value(record, "copy_map_path")
    if copy_map:
        command.extend(["--copy-map", str(Path(copy_map).expanduser().resolve())])
    if copy_map_authoritative:
        command.append("--copy-map-authoritative")
    if strict_evidence:
        command.append("--strict-evidence")
    result = run(command)
    output = result.stdout or "{}"
    report_path.write_text(output if output.endswith("\n") else output + "\n", encoding="utf-8")
    record["validation_report_path"] = str(report_path)
    if result.returncode != 0:
        return False, result.stderr or output, report_path
    return True, "note validation passed", report_path


def run_asset_report(
    record: dict[str, Any],
    work_dir: Path,
    key: str,
    delete_duplicate_unused: bool,
) -> tuple[bool, str, Path | None, dict[str, Any]]:
    note = first_value(record, "note_path", "obsidian_note_path")
    if not note:
        return False, "note_path is missing", None, {}
    note_path = Path(note).expanduser().resolve()
    if not note_path.is_file():
        return False, f"note not found: {note_path}", None, {}
    report_path = Path(
        first_value(record, "asset_report_path")
        or (work_dir / "reports" / f"{key}.asset-report.json")
    ).expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(AUDIT_ASSETS),
        str(note_path),
        "--output",
        str(report_path),
        "--scan-sibling-notes",
    ]
    if first_value(record, "note_assets_dir", "assets_dir_for_note"):
        command.extend(["--assets-dir", first_value(record, "note_assets_dir", "assets_dir_for_note")])
    if delete_duplicate_unused:
        command.append("--delete-duplicate-unused")
    result = run(command)
    if result.returncode != 0:
        return False, result.stderr or result.stdout, report_path, {}
    record["asset_report_path"] = str(report_path)
    report = read_json(report_path)
    return True, "asset report written", report_path, report


def main() -> int:
    args = parse_args()
    requested_stages = [stage.strip() for stage in args.stages.split(",") if stage.strip()]
    unknown = [stage for stage in requested_stages if stage not in STAGES]
    if unknown:
        raise SystemExit(f"Unknown stages: {', '.join(unknown)}")

    work_dir = Path(args.work_dir).expanduser().resolve()
    sidecar_dir = work_dir / "sidecars"
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    papers = load_batch(Path(args.batch_json).expanduser().resolve())
    summary: list[dict[str, Any]] = []
    exit_code = 0

    for index, record in enumerate(papers, start=1):
        key = paper_key(record, index)
        sidecar = sidecar_dir / f"{key}.json"
        paper_summary: dict[str, Any] = {"paper_key": key, "sidecar": str(sidecar), "stages": {}}
        summary.append(paper_summary)

        try:
            if "preflight" in requested_stages:
                ok, message = preflight(record, requested_stages)
                update_sidecar(sidecar, record, "preflight", "complete" if ok else "failed", message)
                paper_summary["stages"]["preflight"] = {"ok": ok, "message": message}
                if not ok:
                    raise RuntimeError(message)

            if "parse_cache" in requested_stages:
                ok, message = run_parse_cache_checkpoint(record)
                update_sidecar(sidecar, record, "parse_cache", "complete" if ok else "failed", message)
                paper_summary["stages"]["parse_cache"] = {"ok": ok, "message": message}
                if not ok:
                    raise RuntimeError(message)

            if "evidence_manifest" in requested_stages:
                ok, message, manifest_path = run_manifest(record, work_dir, key)
                extra = ["--manifest-path", str(manifest_path)] if manifest_path else []
                extra.extend(counts_to_set_args(manifest_counts(manifest_path)))
                update_sidecar(
                    sidecar,
                    record,
                    "evidence_manifest",
                    "complete" if ok else "failed",
                    message,
                    extra,
                )
                paper_summary["stages"]["evidence_manifest"] = {
                    "ok": ok,
                    "message": message,
                    "manifest_path": str(manifest_path) if manifest_path else "",
                    "counts": manifest_counts(manifest_path),
                }
                if not ok:
                    raise RuntimeError(message)

            if "draft" in requested_stages:
                ok, message = run_draft_checkpoint(record)
                update_sidecar(sidecar, record, "draft", "complete" if ok else "failed", message)
                paper_summary["stages"]["draft"] = {"ok": ok, "message": message}
                if not ok:
                    raise RuntimeError(message)

            if "review" in requested_stages:
                status, message = run_review_checkpoint(record)
                update_sidecar(sidecar, record, "review", status, message)
                paper_summary["stages"]["review"] = {
                    "ok": status != "failed",
                    "status": status,
                    "message": message,
                }

            if "validate" in requested_stages:
                ok, message, report_path = run_validation(
                    record,
                    work_dir,
                    key,
                    args.strict_evidence,
                    args.copy_map_authoritative,
                )
                extra = ["--validation-report-path", str(report_path)] if report_path else []
                extra.extend(counts_to_set_args(validation_counts(report_path)))
                extra.extend(fields_to_set_args(validation_sidecar_fields(report_path)))
                update_sidecar(sidecar, record, "validate", "complete" if ok else "failed", message, extra)
                paper_summary["stages"]["validate"] = {
                    "ok": ok,
                    "message": message,
                    "validation_report_path": str(report_path) if report_path else "",
                    "counts": validation_counts(report_path),
                }
                if not ok:
                    raise RuntimeError(message)

            if "cleanup_report" in requested_stages:
                ok, message, report_path, report = run_asset_report(
                    record, work_dir, key, args.delete_duplicate_unused
                )
                extra = ["--asset-report-path", str(report_path)] if report_path else []
                if report:
                    extra.extend(
                        [
                            "--set",
                            f"counts.image_link_count={report.get('image_link_count', 0)}",
                            "--set",
                            f"counts.assets_total={report.get('assets_total', 0)}",
                            "--set",
                            f"counts.referenced_assets_count={report.get('referenced_assets_count', 0)}",
                            "--set",
                            f"counts.unused_assets_count={report.get('unused_assets_count', 0)}",
                            "--set",
                            f"counts.duplicate_hash_count={report.get('duplicate_hash_count', 0)}",
                        ]
                    )
                    extra.extend(fields_to_set_args(asset_sidecar_fields(report)))
                update_sidecar(
                    sidecar,
                    record,
                    "cleanup_report",
                    "complete" if ok else "failed",
                    message,
                    extra,
                )
                paper_summary["stages"]["cleanup_report"] = {
                    "ok": ok,
                    "message": message,
                    "asset_report_path": str(report_path) if report_path else "",
                    "counts": {
                        "image_link_count": report.get("image_link_count", 0),
                        "assets_total": report.get("assets_total", 0),
                        "unused_assets_count": report.get("unused_assets_count", 0),
                        "duplicate_hash_count": report.get("duplicate_hash_count", 0),
                    }
                    if report
                    else {},
                }
                if not ok:
                    raise RuntimeError(message)
        except Exception as exc:
            exit_code = 1
            paper_summary["error"] = str(exc)
            if not args.continue_on_error:
                break

    print(json.dumps({"work_dir": str(work_dir), "papers": summary}, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
