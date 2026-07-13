#!/usr/bin/env python3
"""Run deterministic batch-note pipeline stages and maintain per-paper sidecars.

This helper does not draft prose. It prepares and validates the machine-readable
state around drafting so a Codex run can resume paper-by-paper.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import gate_common


SCRIPT_DIR = Path(__file__).resolve().parent
BUILD_MANIFEST = SCRIPT_DIR / "build_evidence_manifest.py"
VALIDATE_NOTE = SCRIPT_DIR / "validate_note.py"
AUDIT_QUALITY = SCRIPT_DIR / "audit_note_quality.py"
VALIDATE_DOMAIN = SCRIPT_DIR / "validate_domain_consistency.py"
AUDIT_ASSETS = SCRIPT_DIR / "audit_note_assets.py"
AUDIT_UNMATCHED_ASSETS = SCRIPT_DIR / "audit_unmatched_assets.py"
UPDATE_SIDECAR = SCRIPT_DIR / "update_pipeline_sidecar.py"
FINAL_GATE_RUNNER = SCRIPT_DIR / "final_gate_runner.py"

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
        "--fail-on-domain-gate",
        action="store_true",
        help="Treat non-pass domain consistency reports as batch failures.",
    )
    parser.add_argument(
        "--delete-duplicate-unused",
        action="store_true",
        help="When running cleanup_report, delete unused duplicate assets after reporting.",
    )
    parser.add_argument(
        "--fail-on-duplicate-assets",
        action="store_true",
        help="When running cleanup_report, fail the stage if duplicate asset SHA256 groups remain.",
    )
    parser.add_argument(
        "--fail-on-unmatched-assets",
        action="store_true",
        help="When running cleanup_report, fail if source MinerU formula/panel assets are missing from final assets.",
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
    return subprocess.run(command, text=True, capture_output=True, encoding="utf-8", errors="replace")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig", errors="ignore"))


def file_sha256(path: Path | None) -> str:
    if not path or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
            "failed_gates": report.get("failed_gates", []),
            "failed_items": report.get("failed_items", []),
            "repair_scope": report.get("repair_scope", ""),
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


def domain_sidecar_fields(report_path: Path | None) -> dict[str, Any]:
    if not report_path or not report_path.is_file():
        return {}
    report = read_json(report_path)
    return {
        "domain": {
            "status": report.get("status", ""),
            "report_path": str(report_path),
            "detected_domain": report.get("detected_domain", ""),
            "detected_paper_type": report.get("detected_paper_type", ""),
            "paper_type_candidate": report.get("paper_type_candidate", ""),
            "domain_confidence": report.get("domain_confidence", 0),
            "paper_type_confidence": report.get("paper_type_confidence", 0),
            "failed_gates": report.get("failed_gates", []),
            "conflict_fields": report.get("conflict_fields", []),
            "failed_checks": report.get("summary", {}).get("failed_checks", 0),
            "total_checks": report.get("summary", {}).get("total_checks", 0),
        },
        "review_items": [
            {
                "section": f"domain:{item.get('check', '')}",
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


def merge_repair_reports(*reports: dict[str, Any]) -> dict[str, Any]:
    """Merge quality/domain/validation-like reports into one repair context."""
    merged: dict[str, Any] = {
        "status": "pass",
        "repair_plan": [],
        "failed_items": [],
        "failed_gates": [],
        "scores": {},
        "source_reports": [],
        "repair_scope": "",
    }
    rank = {
        "pass": 0,
        "needs_minor_repair": 1,
        "needs_major_repair": 2,
        "needs_regeneration": 3,
    }
    worst_rank = 0
    for index, report in enumerate(reports, start=1):
        if not report:
            continue
        status = str(report.get("status", "") or "needs_major_repair")
        worst_rank = max(worst_rank, rank.get(status, 2))
        label = report.get("label") or report.get("report_type") or f"report_{index}"
        merged["source_reports"].append(
            {
                "label": label,
                "status": status,
                "path": report.get("report_path", ""),
            }
        )
        for gate in report.get("failed_gates", []):
            gate_text = str(gate)
            if gate_text not in merged["failed_gates"]:
                merged["failed_gates"].append(gate_text)
        for key, value in report.get("scores", {}).items():
            merged["scores"][key] = value
        for item in report.get("repair_plan", []):
            copied = dict(item)
            if "section" not in copied and "check" in copied:
                copied["section"] = f"domain:{copied.get('check', '')}"
            copied.setdefault("problem", "")
            copied.setdefault("repair_level", "major" if status != "needs_minor_repair" else "minor")
            copied.setdefault("source_report", label)
            merged["repair_plan"].append(copied)
        for item in report.get("failed_items", []):
            if isinstance(item, dict):
                copied_item = dict(item)
                copied_item.setdefault("source_report", label)
                merged["failed_items"].append(copied_item)
        if report.get("repair_scope") and not merged["repair_scope"]:
            merged["repair_scope"] = report.get("repair_scope")
    for status, value in rank.items():
        if value == worst_rank:
            merged["status"] = status
            break
    return merged


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

    def guidance_for_item(section: str, problem: str) -> str:
        lower = f"{section} {problem}".lower()
        if "math" in lower and "format" in lower:
            return (
                "Patch math-like inline code spans only: convert variables, Greek letters, "
                "subscripts/superscripts, constraints, and formula functions to `$...$` or `$$...$$`; "
                "keep real code, paths, commands, filenames, APIs, and data fields in backticks."
            )
        if "formula" in lower or "equation" in lower:
            return (
                "Rewrite the affected Equation/Loss/Objective entries from the source pack and evidence manifest. "
                "Include formula image or LaTeX, symbol explanations, objective/constraint intuition, method/result "
                "connection, and boundary. Do not stop at a one-sentence formula caption."
            )
        if "evidence" in lower or "caption" in lower or "template" in lower:
            return (
                "Rewrite the affected Figure/Table/Prompt/Case entries as item-specific evidence narratives. "
                "For figures, explain mechanism, elements, claim link, and boundary. For tables, explain setting, "
                "metrics, strongest baselines, gains, costs, fairness, and conclusion strength."
            )
        return problem

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
                "guidance": guidance_for_item(str(section), str(problem)),
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


def build_failed_item_actions(
    failed_items: list[dict[str, Any]],
    repair_scope: str,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for item in failed_items:
        gate = str(item.get("gate", ""))
        label = str(item.get("display_label") or item.get("item_key") or "")
        missing_slots = item.get("missing_slots", [])
        verb = "patch" if repair_scope == "item_patch" else "rewrite"
        if item.get("repair_level") == "regeneration" or repair_scope == "regeneration":
            verb = "regenerate"
        actions.append(
            {
                "section": item.get("display_label") or item.get("item_key") or "evidence item",
                "item_key": item.get("item_key", ""),
                "display_label": label,
                "gate": gate,
                "missing_slots": missing_slots,
                "problem": item.get("required_action", ""),
                "action": verb,
                "guidance": item.get("repair_hint") or item.get("required_action", ""),
                "current_excerpt": item.get("current_excerpt", ""),
                "source_context": item.get("source_context", ""),
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
    repair_scope = str(quality_report.get("repair_scope") or "")
    item_actions = build_failed_item_actions(
        list(quality_report.get("failed_items", [])),
        repair_scope,
    )
    actions = item_actions + build_repair_actions(quality_report.get("repair_plan", []), repair_level)

    # retry_validation lists the stages that should be re-run after the repair
    retry_validation: list[str]
    if repair_level == "regeneration":
        retry_validation = ["validate", "quality", "cleanup_report"]
    else:
        retry_validation = ["validate", "quality"]
    if any(str(gate).startswith("domain") for gate in failed_gates) and "domain" not in retry_validation:
        retry_validation.append("domain")

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
        "repair_scope": repair_scope or ("regeneration" if repair_level == "regeneration" else "section_patch"),
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
    domain_path = first_value(record, "domain_report_path")
    asset_path = first_value(record, "asset_report_path")
    missing = [
        name
        for name, value in {
            "validation_report_path": validation_path,
            "quality_report_path": quality_path,
            "domain_report_path": domain_path,
            "asset_report_path": asset_path,
        }.items()
        if not value or not Path(value).expanduser().is_file()
    ]
    if missing:
        return False, "Missing final delivery reports: " + ", ".join(missing)
    validation = read_json(Path(validation_path).expanduser().resolve())
    quality = read_json(Path(quality_path).expanduser().resolve())
    domain = read_json(Path(domain_path).expanduser().resolve())
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
    if domain.get("status") != "pass":
        msg = f"Domain report is {domain.get('status', 'unknown')}"
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
    if asset.get("status") not in {None, "", "pass"}:
        return False, f"Asset report is {asset.get('status', 'unknown')}"
    failed_asset_gates = asset.get("failed_gates", [])
    if failed_asset_gates:
        return False, "Asset report failed gates: " + ", ".join(map(str, failed_asset_gates))
    unmatched_report = asset.get("unmatched_asset_report")
    if isinstance(unmatched_report, dict) and unmatched_report.get("status") not in {None, "", "pass"}:
        return False, f"Unmatched asset report is {unmatched_report.get('status', 'unknown')}"
    if isinstance(unmatched_report, dict) and unmatched_report.get("failed_gates"):
        return False, "Unmatched asset report failed gates: " + ", ".join(
            map(str, unmatched_report.get("failed_gates", []))
        )
    return True, "final delivery gates passed"


def _paper_failed_gates(paper: dict[str, Any]) -> list[str]:
    gates: list[str] = []
    stages = paper.get("stages", {})
    for stage_name, stage in stages.items():
        if not isinstance(stage, dict):
            continue
        if stage.get("ok") is True:
            continue
        status = str(stage.get("status") or "")
        for gate in stage.get("failed_gates", []) or []:
            gate_text = f"{stage_name}/{gate}" if "/" not in str(gate) else str(gate)
            if gate_text not in gates:
                gates.append(gate_text)
        if status and status != "pass":
            gate_text = f"{stage_name}/{status}"
            if gate_text not in gates:
                gates.append(gate_text)
        elif stage_name in {"validate", "cleanup_report", "final_delivery"} and stage:
            gate_text = f"{stage_name}/failed"
            if gate_text not in gates:
                gates.append(gate_text)
    if paper.get("error") and not gates:
        gates.append("pipeline/error")
    return gates


def _next_action_for_paper(paper: dict[str, Any]) -> str:
    stages = paper.get("stages", {})
    quality = stages.get("quality", {})
    domain = stages.get("domain", {})
    validate = stages.get("validate", {})
    cleanup = stages.get("cleanup_report", {})
    final = stages.get("final_delivery", {})
    failed_gate_candidates = _paper_failed_gates(paper)
    common_action = gate_common.next_action_for_failed_gates(failed_gate_candidates)
    if common_action not in {"none", "manual_review_required"}:
        return common_action
    scope = quality.get("repair_scope")
    failed_gates = set(map(str, quality.get("failed_gates", []) or []))
    domain_gates = set(map(str, domain.get("failed_gates", []) or []))
    if any("paper_type_alignment" in gate for gate in domain_gates):
        return "domain_regeneration"
    if scope in {"item_patch", "section_patch", "regeneration"}:
        return "full_regeneration" if scope == "regeneration" else scope
    if {"formula_depth", "evidence_narrative"} & failed_gates:
        return "item_patch"
    if "evidence_coverage" in failed_gates or (validate and validate.get("ok") is not True):
        return "section_patch"
    if cleanup and cleanup.get("ok") is not True:
        return "asset_repair"
    if final and final.get("ok") is not True:
        return "manual_review_required"
    return "manual_review_required"


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

    gate_clusters: dict[str, int] = {}
    for paper in summary:
        for gate in _paper_failed_gates(paper):
            gate_clusters[gate] = gate_clusters.get(gate, 0) + 1

    lines = [
        "# Batch Final Delivery Report",
        "",
        "## Batch Health",
        "",
        f"- production_mode: `{production_mode}`",
        f"- total_papers: {total}",
        f"- passed_final_delivery: {passed}",
        f"- failed_or_unfinished: {failed}",
        f"- papers_with_repair_attempts: {repaired}",
        f"- unresolved_repairs: {unresolved}",
        "",
        "## Failed Gate Clusters",
        "",
    ]
    if gate_clusters:
        for gate, count in sorted(gate_clusters.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- {gate}: {count} paper(s)")
    else:
        lines.append("- <none>")
    lines.extend(
        [
            "",
            "## Next Repair Queue",
            "",
        ]
    )
    queue_index = 1
    for paper in summary:
        if paper.get("stages", {}).get("final_delivery", {}).get("ok") is True:
            continue
        labels: list[str] = []
        quality = paper.get("stages", {}).get("quality", {})
        for item in quality.get("failed_items", []) or []:
            label = item.get("display_label") or item.get("item_key")
            if label and label not in labels:
                labels.append(str(label))
        action = _next_action_for_paper(paper)
        lines.append(
            f"{queue_index}. `{paper.get('paper_key', '')}` - {action}"
            + (f" - {', '.join(labels[:5])}" if labels else "")
        )
        queue_index += 1
    if queue_index == 1:
        lines.append("- <none>")
    lines.extend(
        [
            "",
            "## Paper Table",
            "",
        "| paper_key | final | quality | domain | validation | repair | cleanup | note/source pack | issue |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for paper in summary:
        stages = paper.get("stages", {})
        final_stage = stages.get("final_delivery", {})
        quality = stages.get("quality", {})
        domain = stages.get("domain", {})
        validate = stages.get("validate", {})
        repair = stages.get("repair", {})
        cleanup = stages.get("cleanup_report", {})
        issue = (
            paper.get("error")
            or final_stage.get("message")
            or quality.get("message")
            or domain.get("message")
            or ""
        )

        # Repair column: rounds completed or "-"
        repair_rounds = repair.get("rounds_completed", 0)
        if repair_rounds > 0:
            repair_level = repair.get("repair_level", "")
            repair_str = f"{repair_rounds}r ({repair_level})"
        else:
            repair_str = "-"

        lines.append(
            "| {paper_key} | {final} | {quality} | {domain} | {validation} | {repair} | {cleanup} | {source_pack} | {issue} |".format(
                paper_key=paper.get("paper_key", ""),
                final="pass" if final_stage.get("ok") else "fail",
                quality=quality.get("status") or ("pass" if quality.get("ok") else ""),
                domain=domain.get("status") or ("pass" if domain.get("ok") else ""),
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


def path_check(path_text: str, *, must_be_file: bool = False, must_be_dir: bool = False) -> str:
    if not path_text:
        return "missing"
    path = Path(path_text).expanduser()
    if must_be_file:
        return "pass" if path.is_file() else "fail"
    if must_be_dir:
        return "pass" if path.is_dir() else "fail"
    return "pass" if path.exists() else "fail"


def source_pack_quality_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    full_md = str(payload.get("full_md_path") or payload.get("source_md") or "")
    content_list = str(payload.get("content_list_path") or payload.get("content_list") or "")
    mineru_manifest = str(payload.get("manifest_json") or "")
    assets_dir = str(payload.get("assets_dir") or "")
    pdf_path = str(payload.get("pdf_path") or "")
    title = str(payload.get("title") or "")
    risk_flags: list[str] = []
    assets_count = 0
    if assets_dir and Path(assets_dir).expanduser().is_dir():
        assets_count = sum(1 for path in Path(assets_dir).expanduser().rglob("*") if path.is_file())
    full_md_size = Path(full_md).expanduser().stat().st_size if full_md and Path(full_md).expanduser().is_file() else 0
    checks = {
        "pdf_exists": path_check(pdf_path, must_be_file=True) if pdf_path else "missing",
        "full_md_exists": path_check(full_md, must_be_file=True),
        "full_md_nonempty": "pass" if full_md_size > 0 else "fail" if full_md else "missing",
        "content_list_exists": path_check(content_list, must_be_file=True),
        "mineru_manifest_exists": path_check(mineru_manifest, must_be_file=True) if mineru_manifest else "missing",
        "assets_dir_exists": path_check(assets_dir, must_be_dir=True),
        "assets_count": assets_count,
        "title_agreement": "unknown" if not title else "pass",
        "reference_boundary_detected": "unknown",
        "post_reference_content_detected": False,
    }
    if assets_dir and assets_count == 0:
        risk_flags.append("low_asset_count")
    if full_md_size == 0:
        risk_flags.append("empty_full_md")
    if checks["content_list_exists"] == "fail":
        risk_flags.append("missing_content_list")
    if checks["assets_dir_exists"] == "fail":
        risk_flags.append("missing_assets_dir")
    status = "fail" if any(checks[key] == "fail" for key in ("full_md_nonempty", "content_list_exists")) else "warning" if risk_flags else "pass"
    return {
        "status": status,
        "checks": checks,
        "risk_flags": risk_flags,
    }


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
        "domain_template": first_value(record, "domain_template", "domain_template_path"),
    }
    payload["source_pack_quality"] = source_pack_quality_from_payload(payload)
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
        "--domain-report-path": first_value(record, "domain_report_path"),
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


def run_domain_precheck(
    record: dict[str, Any],
    work_dir: Path,
    key: str,
) -> tuple[bool, str, Path | None, dict[str, Any]]:
    source_pack = first_value(record, "source_pack_path")
    if not source_pack:
        return False, "source_pack_path is missing", None, {}
    source_pack_path = Path(source_pack).expanduser().resolve()
    if not source_pack_path.is_file():
        return False, f"source pack not found: {source_pack_path}", None, {}
    report_path = Path(
        first_value(record, "domain_precheck_report_path")
        or (work_dir / "reports" / f"{key}.domain-precheck.json")
    ).expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(VALIDATE_DOMAIN),
        "--source-pack",
        str(source_pack_path),
        "--precheck",
        "--json",
    ]
    domain_template = first_value(record, "domain_template", "domain_template_path")
    if domain_template:
        command.extend(["--domain-template", str(Path(domain_template).expanduser().resolve())])
    result = run(command)
    output = result.stdout or "{}"
    report_path.write_text(output if output.endswith("\n") else output + "\n", encoding="utf-8")
    record["domain_precheck_report_path"] = str(report_path)
    try:
        report = read_json(report_path)
    except Exception:
        report = {"status": "fail", "error": "invalid domain precheck output"}
    ok = result.returncode == 0 and report.get("status") in {"pass", "warning"}
    return ok, f"domain precheck status: {report.get('status', 'unknown')}", report_path, report


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


def run_domain(
    record: dict[str, Any],
    work_dir: Path,
    key: str,
) -> tuple[bool, str, Path | None, dict[str, Any]]:
    note = first_value(record, "note_path", "obsidian_note_path")
    if not note:
        return False, "note_path is missing", None, {}
    note_path = Path(note).expanduser().resolve()
    if not note_path.is_file():
        return False, f"note not found: {note_path}", None, {}
    report_path = Path(
        first_value(record, "domain_report_path")
        or (work_dir / "reports" / f"{key}.domain.json")
    ).expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(VALIDATE_DOMAIN), "--note", str(note_path), "--json"]
    source_pack = first_value(record, "source_pack_path")
    if source_pack:
        command.extend(["--source-pack", str(Path(source_pack).expanduser().resolve())])
    domain_template = first_value(record, "domain_template", "domain_template_path")
    if domain_template:
        command.extend(["--domain-template", str(Path(domain_template).expanduser().resolve())])
    result = run(command)
    output = result.stdout or "{}"
    report_path.write_text(output if output.endswith("\n") else output + "\n", encoding="utf-8")
    record["domain_report_path"] = str(report_path)
    try:
        report = read_json(report_path)
    except Exception:
        report = {"status": "needs_major_repair", "repair_plan": []}
    ok = report.get("status") == "pass"
    return ok, f"domain status: {report.get('status', 'unknown')}", report_path, report


def run_asset_report(
    record: dict[str, Any],
    work_dir: Path,
    key: str,
    delete_duplicate_unused: bool,
    fail_on_duplicate_assets: bool,
    fail_on_unmatched_assets: bool,
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
    if fail_on_duplicate_assets:
        command.append("--fail-on-duplicates")
    result = run(command)
    report = read_json(report_path) if report_path.is_file() else {}
    ok = result.returncode == 0
    messages = [result.stderr or result.stdout] if not ok else ["asset report written"]
    record["asset_report_path"] = str(report_path)

    content_list = first_value(record, "content_list", "content_list_path")
    source_assets = first_value(record, "assets_dir", "assets_source_dir", "parser_assets_dir")
    note_assets = first_value(record, "note_assets_dir", "assets_dir_for_note")
    if content_list and source_assets and note_assets:
        unmatched_path = Path(
            first_value(record, "unmatched_asset_report_path")
            or (work_dir / "reports" / f"{key}.unmatched-assets.json")
        ).expanduser().resolve()
        unmatched_command = [
            sys.executable,
            str(AUDIT_UNMATCHED_ASSETS),
            "--content-list",
            str(Path(content_list).expanduser().resolve()),
            "--source-assets-dir",
            str(Path(source_assets).expanduser().resolve()),
            "--note-assets-dir",
            str(Path(note_assets).expanduser().resolve()),
            "--output",
            str(unmatched_path),
        ]
        manifest = first_value(record, "manifest_path")
        if manifest:
            unmatched_command.extend(["--evidence-manifest", str(Path(manifest).expanduser().resolve())])
        if fail_on_unmatched_assets:
            unmatched_command.append("--fail-on-problem-assets")
        unmatched_result = run(unmatched_command)
        unmatched_report = read_json(unmatched_path) if unmatched_path.is_file() else {}
        report["unmatched_asset_report_path"] = str(unmatched_path)
        report["unmatched_asset_report"] = unmatched_report
        record["unmatched_asset_report_path"] = str(unmatched_path)
        if unmatched_result.returncode != 0:
            ok = False
            messages.append(unmatched_result.stderr or unmatched_result.stdout)
        else:
            messages.append("unmatched asset report written")
    if not ok:
        return False, "; ".join(message for message in messages if message), report_path, report
    return True, "; ".join(messages), report_path, report


def run_final_gate(
    record: dict[str, Any],
    work_dir: Path,
    key: str,
    sidecar: Path,
    *,
    strict_evidence: bool,
    copy_map_authoritative: bool,
    delete_duplicate_unused: bool,
    fail_on_duplicate_assets: bool,
    fail_on_unmatched_assets: bool,
    blueprint: Path | None,
) -> tuple[bool, str, Path | None, dict[str, Any]]:
    note = first_value(record, "note_path", "obsidian_note_path")
    if not note:
        return False, "note_path is missing", None, {}
    note_path = Path(note).expanduser().resolve()
    if not note_path.is_file():
        return False, f"note not found: {note_path}", None, {}
    output_path = Path(
        first_value(record, "final_gate_report_path")
        or (work_dir / "reports" / f"{key}.final-gate.json")
    ).expanduser().resolve()
    command = [
        sys.executable,
        str(FINAL_GATE_RUNNER),
        "--paper-key",
        key,
        "--note",
        str(note_path),
        "--reports-dir",
        str(work_dir / "reports"),
        "--output",
        str(output_path),
        "--sidecar",
        str(sidecar),
        "--json",
    ]
    source_pack = first_value(record, "source_pack_path")
    if source_pack:
        command.extend(["--source-pack", str(Path(source_pack).expanduser().resolve())])
    manifest = first_value(record, "manifest_path")
    if manifest:
        command.extend(["--evidence-manifest", str(Path(manifest).expanduser().resolve())])
    copy_map = first_value(record, "copy_map_path")
    if copy_map:
        command.extend(["--copy-map", str(Path(copy_map).expanduser().resolve())])
    content_list = first_value(record, "content_list", "content_list_path")
    if content_list:
        command.extend(["--content-list", str(Path(content_list).expanduser().resolve())])
    source_assets = first_value(record, "assets_dir", "assets_source_dir", "parser_assets_dir")
    if source_assets:
        command.extend(["--source-assets-dir", str(Path(source_assets).expanduser().resolve())])
    note_assets = first_value(record, "note_assets_dir", "assets_dir_for_note")
    if note_assets:
        command.extend(["--note-assets-dir", str(Path(note_assets).expanduser().resolve())])
    if blueprint:
        command.extend(["--blueprint", str(blueprint)])
    if strict_evidence:
        command.append("--strict-evidence")
    if copy_map_authoritative:
        command.append("--copy-map-authoritative")
    if delete_duplicate_unused:
        command.append("--delete-duplicate-unused")
    if fail_on_duplicate_assets:
        command.append("--fail-on-duplicate-assets")
    if fail_on_unmatched_assets:
        command.append("--fail-on-unmatched-assets")
    result = run(command)
    report = read_json(output_path) if output_path.is_file() else {}
    record["final_gate_report_path"] = str(output_path)
    ok = result.returncode == 0 and report.get("status") == "pass"
    if ok:
        return True, "final gate status: pass", output_path, report
    message = result.stderr or result.stdout or f"final gate status: {report.get('status', 'unknown')}"
    return False, message.strip(), output_path if output_path.is_file() else None, report


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
        domain_report_data: dict[str, Any] = {}
        domain_failed_gate = False
        domain_fail_message = ""
        validate_failed = False
        validate_fail_message = ""
        repair_history: list[dict[str, Any]] = []

        try:
            source_pack = write_source_pack(record, work_dir, key)
            paper_summary["source_pack_path"] = str(source_pack)
            source_pack_payload = read_json(source_pack)
            source_quality = source_pack_payload.get("source_pack_quality", {})
            update_sidecar(
                sidecar,
                record,
                "preflight",
                "running",
                "source pack prepared",
                [
                    "--set",
                    f"production_mode={json.dumps(args.production_mode)}",
                    "--set",
                    f"source_pack_quality={json.dumps(source_quality, ensure_ascii=False)}",
                    "--set",
                    f"artifact_hashes.source_pack={json.dumps(file_sha256(source_pack))}",
                ],
            )

            # --------------------------------------------------------------
            # preflight
            # --------------------------------------------------------------
            if "preflight" in requested_stages:
                ok, message = preflight(record, requested_stages)
                if source_quality.get("status") == "fail":
                    ok = False
                    message = "source_pack_quality failed: " + ", ".join(
                        source_quality.get("risk_flags", [])
                    )
                update_sidecar(
                    sidecar,
                    record,
                    "preflight",
                    "complete" if ok else "failed",
                    message,
                    [
                        "--set",
                        f"source_pack_quality={json.dumps(source_quality, ensure_ascii=False)}",
                    ],
                )
                paper_summary["stages"]["preflight"] = {
                    "ok": ok,
                    "message": message,
                    "source_pack_quality": source_quality,
                }
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
                if manifest_path:
                    extra.extend(
                        [
                            "--set",
                            f"artifact_hashes.evidence_manifest={json.dumps(file_sha256(manifest_path))}",
                        ]
                    )
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
            # domain_precheck
            # --------------------------------------------------------------
            if "domain_precheck" in requested_stages:
                ok, message, report_path, report = run_domain_precheck(record, work_dir, key)
                extra_args = []
                if report_path:
                    extra_args.extend(
                        [
                            "--set",
                            f"paths.domain_precheck_report_path={json.dumps(str(report_path))}",
                            "--set",
                            f"domain_precheck={json.dumps(report, ensure_ascii=False)}",
                        ]
                    )
                paper_summary["stages"]["domain_precheck"] = {
                    "ok": ok,
                    "message": message,
                    "domain_precheck_report_path": str(report_path) if report_path else "",
                    "status": report.get("status", "") if report else "",
                    "paper_type_candidate": report.get("paper_type_candidate", "") if report else "",
                    "confidence": report.get("confidence", "") if report else "",
                }
                update_sidecar(
                    sidecar,
                    record,
                    "domain_precheck",
                    "complete" if ok else "failed",
                    message,
                    extra_args,
                )
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
                    "failed_gates": report.get("failed_gates", []) if report else [],
                    "failed_items": report.get("failed_items", []) if report else [],
                    "repair_scope": report.get("repair_scope", "") if report else "",
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
            # domain
            # --------------------------------------------------------------
            if "domain" in requested_stages:
                ok, message, report_path, report = run_domain(record, work_dir, key)
                domain_report_data = report
                extra_args = ["--domain-report-path", str(report_path)] if report_path else []
                extra_args.extend(fields_to_set_args(domain_sidecar_fields(report_path)))
                paper_summary["stages"]["domain"] = {
                    "ok": ok,
                    "message": message,
                    "domain_report_path": str(report_path) if report_path else "",
                    "status": report.get("status", "") if report else "",
                    "detected_domain": report.get("detected_domain", "") if report else "",
                    "detected_paper_type": report.get("detected_paper_type", "") if report else "",
                    "paper_type_candidate": report.get("paper_type_candidate", "") if report else "",
                    "failed_gates": report.get("failed_gates", []) if report else [],
                    "conflict_fields": report.get("conflict_fields", []) if report else [],
                }
                if not ok and args.fail_on_domain_gate:
                    if repair_rounds > 0:
                        domain_failed_gate = True
                        domain_fail_message = message
                        update_sidecar(
                            sidecar,
                            record,
                            "domain",
                            "failed",
                            message,
                            extra_args,
                        )
                    else:
                        update_sidecar(
                            sidecar,
                            record,
                            "domain",
                            "failed",
                            message,
                            extra_args,
                        )
                        raise RuntimeError(message)
                else:
                    update_sidecar(
                        sidecar,
                        record,
                        "domain",
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
                    "failed_gates": [
                        item.get("kind", "validation_error")
                        for item in (read_json(report_path).get("errors", []) if report_path and report_path.is_file() else [])
                    ],
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
            if repair_rounds > 0 and (quality_failed_gate or domain_failed_gate or validate_failed):
                # Merge all failed gate reports into one repair context.
                repair_reports: list[dict[str, Any]] = []
                if quality_report_data:
                    quality_context = dict(quality_report_data)
                    quality_context["label"] = "quality"
                    repair_reports.append(quality_context)
                if domain_report_data:
                    domain_context = dict(domain_report_data)
                    domain_context["label"] = "domain"
                    repair_reports.append(domain_context)
                if validate_failed and not repair_reports:
                    repair_reports.append(
                        {
                            "label": "validation",
                            "status": "needs_major_repair",
                            "repair_plan": [],
                            "scores": {},
                        }
                    )
                qr = merge_repair_reports(*repair_reports)

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
                if domain_failed_gate:
                    raise RuntimeError(
                        f"Domain gate failed after {repair_rounds} repair round(s): "
                        f"{domain_fail_message}"
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
                if domain_failed_gate:
                    raise RuntimeError(domain_fail_message)
                if validate_failed:
                    raise RuntimeError(validate_fail_message)

            # --------------------------------------------------------------
            # cleanup_report
            # --------------------------------------------------------------
            if "cleanup_report" in requested_stages:
                ok, message, report_path, report = run_asset_report(
                    record,
                    work_dir,
                    key,
                    args.delete_duplicate_unused,
                    args.fail_on_duplicate_assets,
                    args.fail_on_unmatched_assets,
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
                    unmatched_report = report.get("unmatched_asset_report")
                    if isinstance(unmatched_report, dict):
                        extra_args.extend(
                            [
                                "--set",
                                f"counts.unmatched_source_asset_count={unmatched_report.get('missing_count', 0)}",
                                "--set",
                                f"counts.unmatched_problem_asset_count={unmatched_report.get('problem_count', 0)}",
                            ]
                        )
                        extra_args.extend(
                            fields_to_set_args(
                                {
                                    "paths.unmatched_asset_report_path": report.get(
                                        "unmatched_asset_report_path", ""
                                    ),
                                    "asset_unmatched.failed_gates": ",".join(
                                        unmatched_report.get("failed_gates", [])
                                    ),
                                }
                            )
                        )
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
                    "failed_gates": report.get("failed_gates", []) if report else [],
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
                ok, message, report_path, report = run_final_gate(
                    record,
                    work_dir,
                    key,
                    sidecar,
                    strict_evidence=args.strict_evidence,
                    copy_map_authoritative=args.copy_map_authoritative,
                    delete_duplicate_unused=args.delete_duplicate_unused,
                    fail_on_duplicate_assets=args.fail_on_duplicate_assets,
                    fail_on_unmatched_assets=args.fail_on_unmatched_assets,
                    blueprint=blueprint,
                )
                paper_summary["stages"]["final_delivery"] = {
                    "ok": ok,
                    "message": message,
                    "final_gate_report_path": str(report_path) if report_path else "",
                    "status": report.get("status", "") if report else "",
                    "failed_gates": report.get("failed_gates", []) if report else [],
                    "next_action": report.get("next_action", "") if report else "",
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
