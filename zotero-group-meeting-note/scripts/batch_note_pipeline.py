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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
BUILD_MANIFEST = SCRIPT_DIR / "build_evidence_manifest.py"
VALIDATE_NOTE = SCRIPT_DIR / "validate_note.py"
AUDIT_QUALITY = SCRIPT_DIR / "audit_note_quality.py"
AUDIT_ASSETS = SCRIPT_DIR / "audit_note_assets.py"
UPDATE_SIDECAR = SCRIPT_DIR / "update_pipeline_sidecar.py"

STAGES = [
    "preflight",
    "parse_cache",
    "evidence_manifest",
    "draft",
    "review",
    "quality",
    "validate",
    "repair",
    "cleanup_report",
    "final_delivery",
]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# ---------------------------------------------------------------------------
# Quality-report status to repair-level mapping
# ---------------------------------------------------------------------------

_QUALITY_STATUS_REPAIR_MAP: dict[str, str] = {
    "needs_minor_repair": "minor",
    "needs_major_repair": "major",
    "needs_regeneration": "regeneration",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================================================================
# CLI
# ============================================================================


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
        "--production-mode",
        choices=["single-final", "batch-final-controlled"],
        default="batch-final-controlled",
        help="Production mode recorded in reports and sidecars.",
    )
    parser.add_argument(
        "--blueprint",
        default=str(SCRIPT_DIR.parent / "references" / "blueprint.md"),
        help="Blueprint structure contract used by validation/quality gates.",
    )
    parser.add_argument(
        "--final-report",
        help="Optional Markdown batch delivery report path.",
    )
    parser.add_argument(
        "--fail-on-quality-gate",
        action="store_true",
        help="Treat non-pass quality reports as batch failures.",
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
    parser.add_argument(
        "--repair-rounds",
        type=int,
        default=0,
        help="Maximum repair rounds when quality/validation fail (0-2, default 0).",
    )
    return parser.parse_args()


# ============================================================================
# Helpers
# ============================================================================


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


def quality_sidecar_fields(report_path: Path | None) -> dict[str, Any]:
    if not report_path or not report_path.is_file():
        return {}
    report = read_json(report_path)
    return {
        "quality": {
            "status": report.get("status", ""),
            "report_path": str(report_path),
            "repair_plan_count": len(report.get("repair_plan", [])),
            "scores": report.get("scores", {}),
        },
        "review_items": [
            {
                "section": item.get("section", ""),
                "problem": item.get("problem", ""),
                "repair_level": item.get("repair_level", ""),
            }
            for item in report.get("repair_plan", [])
        ],
    }


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


# ============================================================================
# Repair helpers
# ============================================================================


def determine_repair_level(quality_report: dict[str, Any]) -> str:
    """Map a quality report status to a repair level string."""
    status = (quality_report.get("status") or "").strip()
    return _QUALITY_STATUS_REPAIR_MAP.get(status, "major")


def _derive_failed_gates(quality_report: dict[str, Any]) -> list[str]:
    """Extract likely failed gates from the quality report."""
    gates: list[str] = []

    # 1) Explicit failed_gates list in the report
    explicit = quality_report.get("failed_gates")
    if isinstance(explicit, list) and explicit:
        return [str(g) for g in explicit]

    # 2) Derive from repair_plan section names
    for item in quality_report.get("repair_plan", []):
        section = str(item.get("section", "")).strip()
        if section and section not in gates:
            gates.append(section)

    # 3) Derive from scores: numeric scores < 1.0 or string scores != "pass"
    scores = quality_report.get("scores", {})
    if isinstance(scores, dict):
        for key, value in scores.items():
            if isinstance(value, (int, float)) and value < 1.0:
                if key not in gates:
                    gates.append(key)
            elif isinstance(value, str) and value.lower() != "pass":
                if key not in gates:
                    gates.append(key)

    return gates


def build_repair_actions(
    repair_plan: list[dict[str, Any]], repair_level: str
) -> list[dict[str, Any]]:
    """Convert quality-report repair_plan items into repair-instruction actions."""
    actions: list[dict[str, Any]] = []

    action_kind: str
    if repair_level == "minor":
        action_kind = "patch"
    elif repair_level == "regeneration":
        action_kind = "regenerate"
    else:
        action_kind = "rewrite"

    for item in repair_plan:
        section = item.get("section", "")
        problem = item.get("problem", "")
        item_level = item.get("repair_level", "")

        # Use the per-item repair_level to refine the action verb
        if item_level == "minor":
            verb = "patch"
        elif item_level == "major":
            verb = "rewrite"
        elif item_level == "regeneration":
            verb = "regenerate"
        else:
            verb = action_kind

        actions.append(
            {
                "section": section,
                "problem": problem,
                "action": verb,
                "guidance": problem,
            }
        )

    # Fallback when the repair_plan is empty but the report signals non-pass
    if not actions and repair_level in ("major", "regeneration"):
        actions.append(
            {
                "section": "entire note",
                "problem": "Quality report signals major issues requiring full rewrite or regeneration.",
                "action": "regenerate" if repair_level == "regeneration" else "rewrite",
                "guidance": (
                    "Review the quality report and blueprint for full requirements. "
                    "Rebuild the note from the evidence manifest and source material."
                ),
            }
        )
    elif not actions:
        actions.append(
            {
                "section": "entire note",
                "problem": "Quality report indicates minor issues that need targeted patching.",
                "action": "patch",
                "guidance": "Apply small targeted edits per the quality report findings.",
            }
        )

    return actions


def write_repair_instruction(
    work_dir: Path,
    key: str,
    quality_report: dict[str, Any],
    repair_round: int,
    max_rounds: int,
) -> Path:
    """Write a structured repair-instruction JSON file for external repair agents.

    Returns the path to the written file.
    """
    repair_level = determine_repair_level(quality_report)
    failed_gates = _derive_failed_gates(quality_report)
    actions = build_repair_actions(quality_report.get("repair_plan", []), repair_level)

    # retry_validation lists the stages that should be re-run after the repair
    retry_validation: list[str]
    if repair_level == "regeneration":
        retry_validation = ["validate", "quality", "cleanup_report"]
    else:
        retry_validation = ["validate", "quality"]

    instruction: dict[str, Any] = {
        "schema_version": 1,
        "paper_key": key,
        "repair_round": repair_round,
        "max_rounds": max_rounds,
        "trigger": {
            "quality_status": quality_report.get("status", ""),
            "failed_gates": failed_gates,
        },
        "repair_level": repair_level,
        "actions": actions,
        "retry_validation": retry_validation,
        "created_at": _now_iso(),
    }

    instruction_path = work_dir / "reports" / f"{key}.repair-instruction.json"
    instruction_path.parent.mkdir(parents=True, exist_ok=True)
    instruction_path.write_text(
        json.dumps(instruction, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return instruction_path


def repair_sidecar_fields(
    round_num: int,
    repair_level: str,
    instruction_path: Path,
    history: list[dict[str, Any]],
) -> list[str]:
    """Return --set arguments to persist repair state in the sidecar."""
    return [
        "--set",
        f"repair.rounds_completed={json.dumps(round_num)}",
        "--set",
        f"repair.repair_level={json.dumps(repair_level)}",
        "--set",
        f"repair.instruction_path={json.dumps(str(instruction_path))}",
        "--set",
        f"repair.history={json.dumps(history, ensure_ascii=False)}",
    ]


# ============================================================================
# Final delivery
# ============================================================================


def final_delivery_status(
    record: dict[str, Any],
    repair_info: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    validation_path = first_value(record, "validation_report_path")
    quality_path = first_value(record, "quality_report_path")
    asset_path = first_value(record, "asset_report_path")
    missing = [
        name
        for name, value in {
            "validation_report_path": validation_path,
            "quality_report_path": quality_path,
            "asset_report_path": asset_path,
        }.items()
        if not value or not Path(value).expanduser().is_file()
    ]
    if missing:
        return False, "Missing final delivery reports: " + ", ".join(missing)
    validation = read_json(Path(validation_path).expanduser().resolve())
    quality = read_json(Path(quality_path).expanduser().resolve())
    asset = read_json(Path(asset_path).expanduser().resolve())
    if validation.get("status") != "pass":
        msg = "Validation report is not pass"
        if repair_info and repair_info.get("rounds_completed", 0) > 0:
            msg += (
                f" | Unresolved repairs after {repair_info['rounds_completed']} round(s)"
            )
        return False, msg
    if quality.get("status") != "pass":
        msg = f"Quality report is {quality.get('status', 'unknown')}"
        if repair_info and repair_info.get("rounds_completed", 0) > 0:
            msg += (
                f" | Unresolved repairs after {repair_info['rounds_completed']} round(s)"
            )
        return False, msg
    if int(asset.get("unused_assets_count", 0) or 0) and int(asset.get("image_link_count", 0) or 0) == 0:
        msg = "Asset report has unused assets but no note image links"
        if repair_info and repair_info.get("rounds_completed", 0) > 0:
            msg += (
                f" | Unresolved repairs after {repair_info['rounds_completed']} round(s)"
            )
        return False, msg
    return True, "final delivery gates passed"


def write_final_report(path: Path, summary: list[dict[str, Any]], production_mode: str) -> None:
    total = len(summary)
    passed = sum(
        1
        for paper in summary
        if paper.get("stages", {}).get("final_delivery", {}).get("ok") is True
    )
    failed = total - passed
    repaired = sum(
        1
        for paper in summary
        if paper.get("stages", {}).get("repair", {}).get("rounds_completed", 0) > 0
    )
    unresolved = sum(
        1
        for paper in summary
        if paper.get("stages", {}).get("repair", {}).get("rounds_completed", 0) > 0
        and paper.get("stages", {}).get("final_delivery", {}).get("ok") is not True
    )

    lines = [
        "# Batch Final Delivery Report",
        "",
        f"- production_mode: `{production_mode}`",
        f"- total_papers: {total}",
        f"- passed_final_delivery: {passed}",
        f"- failed_or_unfinished: {failed}",
        f"- papers_with_repair_attempts: {repaired}",
        f"- unresolved_repairs: {unresolved}",
        "",
        "| paper_key | final | quality | validation | repair | cleanup | note/source pack | issue |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for paper in summary:
        stages = paper.get("stages", {})
        final_stage = stages.get("final_delivery", {})
        quality = stages.get("quality", {})
        validate = stages.get("validate", {})
        repair = stages.get("repair", {})
        cleanup = stages.get("cleanup_report", {})
        issue = paper.get("error") or final_stage.get("message") or quality.get("message") or ""

        # Repair column: rounds completed or "-"
        repair_rounds = repair.get("rounds_completed", 0)
        if repair_rounds > 0:
            repair_level = repair.get("repair_level", "")
            repair_str = f"{repair_rounds}r ({repair_level})"
        else:
            repair_str = "-"

        lines.append(
            "| {paper_key} | {final} | {quality} | {validation} | {repair} | {cleanup} | {source_pack} | {issue} |".format(
                paper_key=paper.get("paper_key", ""),
                final="pass" if final_stage.get("ok") else "fail",
                quality=quality.get("status") or ("pass" if quality.get("ok") else ""),
                validation="pass" if validate.get("ok") else "fail" if validate else "",
                repair=repair_str,
                cleanup="pass" if cleanup.get("ok") else "fail" if cleanup else "",
                source_pack=paper.get("source_pack_path", ""),
                issue=str(issue).replace("|", "\\|"),
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ============================================================================
# Stage runners
# ============================================================================


def source_pack_path_for(record: dict[str, Any], work_dir: Path, key: str) -> Path:
    explicit = first_value(record, "source_pack_path")
    if explicit:
        return Path(explicit).expanduser().resolve()
    return (work_dir / "source-packs" / f"{key}.source-pack.json").resolve()


def write_source_pack(record: dict[str, Any], work_dir: Path, key: str) -> Path:
    path = source_pack_path_for(record, work_dir, key)
    payload = {
        "paper_key": first_value(record, "paper_key", "key", "id") or key,
        "title": first_value(record, "title"),
        "pdf_path": first_value(record, "pdf_path"),
        "source_md": first_value(record, "source_md", "full_md_path", "full_md"),
        "full_md_path": first_value(record, "source_md", "full_md_path", "full_md"),
        "content_list": first_value(record, "content_list", "content_list_path"),
        "content_list_path": first_value(record, "content_list", "content_list_path"),
        "manifest_json": first_value(record, "parser_manifest", "manifest_json"),
        "assets_dir": first_value(record, "assets_dir"),
        "assets_source_dir": first_value(record, "assets_dir"),
        "note_path": first_value(record, "note_path", "obsidian_note_path"),
        "note_assets_dir": first_value(record, "note_assets_dir", "assets_dir_for_note"),
        "copy_map_path": first_value(record, "copy_map_path"),
        "evidence_manifest_path": first_value(record, "manifest_path"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    record["source_pack_path"] = str(path)
    return path


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
        "--quality-report-path": first_value(record, "quality_report_path"),
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


def run_manifest(
    record: dict[str, Any], work_dir: Path, key: str, source_pack_path: Path | None = None
) -> tuple[bool, str, Path | None]:
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
    if source_pack_path:
        command.extend(["--source-pack", str(source_pack_path)])
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
    blueprint: Path | None,
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
    if blueprint:
        command.extend(["--blueprint", str(blueprint)])
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


def run_quality(
    record: dict[str, Any],
    work_dir: Path,
    key: str,
    blueprint: Path | None,
) -> tuple[bool, str, Path | None, dict[str, Any]]:
    note = first_value(record, "note_path", "obsidian_note_path")
    if not note:
        return False, "note_path is missing", None, {}
    note_path = Path(note).expanduser().resolve()
    if not note_path.is_file():
        return False, f"note not found: {note_path}", None, {}
    report_path = Path(
        first_value(record, "quality_report_path")
        or (work_dir / "reports" / f"{key}.quality.json")
    ).expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(AUDIT_QUALITY), "--note", str(note_path), "--json"]
    source_pack = first_value(record, "source_pack_path")
    if source_pack:
        command.extend(["--source-pack", str(Path(source_pack).expanduser().resolve())])
    manifest = first_value(record, "manifest_path")
    if manifest:
        command.extend(["--evidence-manifest", str(Path(manifest).expanduser().resolve())])
    if blueprint:
        command.extend(["--blueprint", str(blueprint)])
    result = run(command)
    output = result.stdout or "{}"
    report_path.write_text(output if output.endswith("\n") else output + "\n", encoding="utf-8")
    record["quality_report_path"] = str(report_path)
    try:
        report = read_json(report_path)
    except Exception:
        report = {"status": "needs_major_repair", "repair_plan": []}
    ok = report.get("status") == "pass"
    return ok, f"quality status: {report.get('status', 'unknown')}", report_path, report


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


# ============================================================================
# Main
# ============================================================================


def main() -> int:
    args = parse_args()
    requested_stages = [stage.strip() for stage in args.stages.split(",") if stage.strip()]
    unknown = [stage for stage in requested_stages if stage not in STAGES]
    if unknown:
        raise SystemExit(f"Unknown stages: {', '.join(unknown)}")

    # Clamp --repair-rounds to 0-2
    repair_rounds = max(0, min(args.repair_rounds, 2))
    if args.repair_rounds > 2:
        print(
            f"Warning: --repair-rounds={args.repair_rounds} exceeds max 2; "
            f"clamping to 2.",
            file=sys.stderr,
        )

    work_dir = Path(args.work_dir).expanduser().resolve()
    blueprint = Path(args.blueprint).expanduser().resolve() if args.blueprint else None
    sidecar_dir = work_dir / "sidecars"
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    papers = load_batch(Path(args.batch_json).expanduser().resolve())
    summary: list[dict[str, Any]] = []
    exit_code = 0

    for index, record in enumerate(papers, start=1):
        key = paper_key(record, index)
        sidecar = sidecar_dir / f"{key}.json"
        paper_summary: dict[str, Any] = {
            "paper_key": key,
            "sidecar": str(sidecar),
            "stages": {},
        }
        summary.append(paper_summary)

        # ------------------------------------------------------------------
        # Per-paper state for deferred failure / repair
        # ------------------------------------------------------------------
        quality_report_data: dict[str, Any] = {}
        quality_failed_gate = False
        quality_fail_message = ""
        validate_failed = False
        validate_fail_message = ""
        repair_history: list[dict[str, Any]] = []

        try:
            source_pack = write_source_pack(record, work_dir, key)
            paper_summary["source_pack_path"] = str(source_pack)
            update_sidecar(
                sidecar,
                record,
                "preflight",
                "running",
                "source pack prepared",
                ["--set", f"production_mode={json.dumps(args.production_mode)}"],
            )

            # --------------------------------------------------------------
            # preflight
            # --------------------------------------------------------------
            if "preflight" in requested_stages:
                ok, message = preflight(record, requested_stages)
                update_sidecar(
                    sidecar, record, "preflight", "complete" if ok else "failed", message
                )
                paper_summary["stages"]["preflight"] = {"ok": ok, "message": message}
                if not ok:
                    raise RuntimeError(message)

            # --------------------------------------------------------------
            # parse_cache
            # --------------------------------------------------------------
            if "parse_cache" in requested_stages:
                ok, message = run_parse_cache_checkpoint(record)
                update_sidecar(
                    sidecar, record, "parse_cache", "complete" if ok else "failed", message
                )
                paper_summary["stages"]["parse_cache"] = {"ok": ok, "message": message}
                if not ok:
                    raise RuntimeError(message)

            # --------------------------------------------------------------
            # evidence_manifest
            # --------------------------------------------------------------
            if "evidence_manifest" in requested_stages:
                ok, message, manifest_path = run_manifest(record, work_dir, key, source_pack)
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

            # --------------------------------------------------------------
            # draft
            # --------------------------------------------------------------
            if "draft" in requested_stages:
                ok, message = run_draft_checkpoint(record)
                update_sidecar(
                    sidecar, record, "draft", "complete" if ok else "failed", message
                )
                paper_summary["stages"]["draft"] = {"ok": ok, "message": message}
                if not ok:
                    raise RuntimeError(message)

            # --------------------------------------------------------------
            # review
            # --------------------------------------------------------------
            if "review" in requested_stages:
                status, message = run_review_checkpoint(record)
                update_sidecar(sidecar, record, "review", status, message)
                paper_summary["stages"]["review"] = {
                    "ok": status != "failed",
                    "status": status,
                    "message": message,
                }

            # --------------------------------------------------------------
            # quality
            # --------------------------------------------------------------
            if "quality" in requested_stages:
                ok, message, report_path, report = run_quality(
                    record, work_dir, key, blueprint
                )
                quality_report_data = report
                extra_args = ["--quality-report-path", str(report_path)] if report_path else []
                extra_args.extend(fields_to_set_args(quality_sidecar_fields(report_path)))
                paper_summary["stages"]["quality"] = {
                    "ok": ok,
                    "message": message,
                    "quality_report_path": str(report_path) if report_path else "",
                    "status": report.get("status", "") if report else "",
                }

                if not ok and args.fail_on_quality_gate:
                    if repair_rounds > 0:
                        # Defer the raise --- repair loop will handle it
                        quality_failed_gate = True
                        quality_fail_message = message
                        update_sidecar(
                            sidecar,
                            record,
                            "quality",
                            "failed",
                            message,
                            extra_args,
                        )
                    else:
                        update_sidecar(
                            sidecar,
                            record,
                            "quality",
                            "failed",
                            message,
                            extra_args,
                        )
                        raise RuntimeError(message)
                else:
                    update_sidecar(
                        sidecar,
                        record,
                        "quality",
                        "complete" if ok else "failed",
                        message,
                        extra_args,
                    )

            # --------------------------------------------------------------
            # validate
            # --------------------------------------------------------------
            if "validate" in requested_stages:
                ok, message, report_path = run_validation(
                    record,
                    work_dir,
                    key,
                    args.strict_evidence,
                    args.copy_map_authoritative,
                    blueprint,
                )
                extra_args = ["--validation-report-path", str(report_path)] if report_path else []
                extra_args.extend(counts_to_set_args(validation_counts(report_path)))
                extra_args.extend(fields_to_set_args(validation_sidecar_fields(report_path)))
                paper_summary["stages"]["validate"] = {
                    "ok": ok,
                    "message": message,
                    "validation_report_path": str(report_path) if report_path else "",
                    "counts": validation_counts(report_path),
                }

                if not ok:
                    if repair_rounds > 0:
                        # Defer the raise --- repair loop will handle it
                        validate_failed = True
                        validate_fail_message = message
                        update_sidecar(
                            sidecar,
                            record,
                            "validate",
                            "failed",
                            message,
                            extra_args,
                        )
                    else:
                        update_sidecar(
                            sidecar,
                            record,
                            "validate",
                            "failed",
                            message,
                            extra_args,
                        )
                        raise RuntimeError(message)
                else:
                    update_sidecar(
                        sidecar,
                        record,
                        "validate",
                        "complete",
                        message,
                        extra_args,
                    )

            # --------------------------------------------------------------
            # repair (automatic when repair_rounds > 0 and a gate failed)
            # --------------------------------------------------------------
            if repair_rounds > 0 and (quality_failed_gate or validate_failed):
                # Use the quality report if available; otherwise build a minimal
                # report from the validation failure context.
                qr = quality_report_data if quality_report_data else {}
                if not qr:
                    qr = {
                        "status": "needs_major_repair",
                        "repair_plan": [],
                        "scores": {},
                    }

                repair_level = determine_repair_level(qr)

                for round_num in range(1, repair_rounds + 1):
                    instruction_path = write_repair_instruction(
                        work_dir, key, qr, round_num, repair_rounds
                    )
                    entry: dict[str, Any] = {
                        "round": round_num,
                        "repair_level": repair_level,
                        "instruction_path": str(instruction_path),
                        "quality_status": qr.get("status", ""),
                        "timestamp": _now_iso(),
                    }
                    repair_history.append(entry)

                    # Update sidecar with repair state after each round
                    update_sidecar(
                        sidecar,
                        record,
                        "repair",
                        "complete",
                        (
                            f"Repair round {round_num}/{repair_rounds} "
                            f"instruction written ({repair_level})"
                        ),
                        repair_sidecar_fields(
                            round_num, repair_level, instruction_path, repair_history
                        ),
                    )

                paper_summary["stages"]["repair"] = {
                    "ok": False,
                    "rounds_completed": repair_rounds,
                    "repair_level": repair_level,
                    "history": repair_history,
                    "message": (
                        f"Repair instructions written ({repair_rounds} round(s)), "
                        "awaiting external repair"
                    ),
                }

                # Still raise after repair loop so the batch runner knows
                # this paper needs attention.
                if quality_failed_gate:
                    raise RuntimeError(
                        f"Quality gate failed after {repair_rounds} repair round(s): "
                        f"{quality_fail_message}"
                    )
                if validate_failed:
                    raise RuntimeError(
                        f"Validation failed after {repair_rounds} repair round(s): "
                        f"{validate_fail_message}"
                    )

            # If repair_rounds == 0 but flags are somehow set (should not
            # happen because we raise inline above), raise now.
            if repair_rounds == 0:
                if quality_failed_gate:
                    raise RuntimeError(quality_fail_message)
                if validate_failed:
                    raise RuntimeError(validate_fail_message)

            # --------------------------------------------------------------
            # cleanup_report
            # --------------------------------------------------------------
            if "cleanup_report" in requested_stages:
                ok, message, report_path, report = run_asset_report(
                    record, work_dir, key, args.delete_duplicate_unused
                )
                extra_args = ["--asset-report-path", str(report_path)] if report_path else []
                if report:
                    extra_args.extend(
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
                    extra_args.extend(fields_to_set_args(asset_sidecar_fields(report)))
                update_sidecar(
                    sidecar,
                    record,
                    "cleanup_report",
                    "complete" if ok else "failed",
                    message,
                    extra_args,
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

            # --------------------------------------------------------------
            # final_delivery
            # --------------------------------------------------------------
            if "final_delivery" in requested_stages:
                repair_info: dict[str, Any] = {
                    "rounds_completed": len(repair_history),
                }
                ok, message = final_delivery_status(record, repair_info)
                update_sidecar(
                    sidecar,
                    record,
                    "final_delivery",
                    "complete" if ok else "failed",
                    message,
                    ["--set", f"final_status={json.dumps('pass' if ok else 'fail')}"],
                )
                paper_summary["stages"]["final_delivery"] = {
                    "ok": ok,
                    "message": message,
                }
                if not ok:
                    raise RuntimeError(message)
        except Exception as exc:
            exit_code = 1
            paper_summary["error"] = str(exc)
            if not args.continue_on_error:
                break

    if args.final_report:
        write_final_report(
            Path(args.final_report).expanduser().resolve(),
            summary,
            args.production_mode,
        )

    print(json.dumps({"work_dir": str(work_dir), "papers": summary}, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
