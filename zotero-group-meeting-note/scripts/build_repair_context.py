#!/usr/bin/env python3
"""Build an item-level repair context from gate reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge quality/domain/validation reports into a compact repair context."
    )
    parser.add_argument("--paper-key", required=True, help="Single paper key.")
    parser.add_argument("--source-pack", help="source_pack.json path.")
    parser.add_argument("--evidence-manifest", help="evidence_manifest.json path.")
    parser.add_argument("--copy-map", help="copy_map.json path.")
    parser.add_argument("--note", help="Current note path.")
    parser.add_argument("--quality-report", help="audit_note_quality.py JSON report.")
    parser.add_argument("--domain-report", help="validate_domain_consistency.py JSON report.")
    parser.add_argument("--validation-report", help="validate_note.py JSON report.")
    parser.add_argument("--asset-report", help="audit_note_assets.py JSON report.")
    parser.add_argument("--output", help="Optional JSON output path.")
    return parser.parse_args()


def read_json(path_text: str | None) -> dict[str, Any]:
    if not path_text:
        return {}
    path = Path(path_text).expanduser().resolve()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig", errors="ignore"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def repair_scope(reports: list[dict[str, Any]]) -> str:
    scopes = [str(report.get("repair_scope", "")) for report in reports if report]
    if "regeneration" in scopes:
        return "regeneration"
    if "domain_regeneration" in scopes:
        return "domain_regeneration"
    if "section_patch" in scopes:
        return "section_patch"
    if "item_patch" in scopes:
        return "item_patch"
    if any(report.get("status") == "needs_regeneration" for report in reports):
        return "domain_regeneration"
    return "manual_review_required"


def failed_items_from_validation(report: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in report.get("errors", []) + report.get("warnings", []):
        kind = str(row.get("kind", ""))
        if kind not in {
            "missing_required_evidence",
            "missing_evidence_reference",
            "missing_evidence_asset_link",
            "misplaced_evidence_asset_link",
            "missing_copy_map_entry",
            "evidence_order_error",
        }:
            continue
        items.append(
            {
                "gate": "evidence_coverage",
                "item_key": "",
                "display_label": "",
                "repair_level": "major",
                "missing_slots": [kind],
                "current_excerpt": "",
                "source_context": "",
                "required_action": str(row.get("message", "")),
            }
        )
    return items


def main() -> int:
    args = parse_args()
    quality = read_json(args.quality_report)
    domain = read_json(args.domain_report)
    validation = read_json(args.validation_report)
    asset = read_json(args.asset_report)
    reports = [quality, domain, validation, asset]

    failed_items: list[dict[str, Any]] = []
    failed_items.extend(quality.get("failed_items", []) if isinstance(quality.get("failed_items"), list) else [])
    failed_items.extend(failed_items_from_validation(validation))

    failed_gates: list[str] = []
    for report_name, report in [
        ("quality", quality),
        ("domain", domain),
        ("validation", validation),
        ("asset", asset),
    ]:
        if not report:
            continue
        for gate in report.get("failed_gates", []):
            gate_text = f"{report_name}/{gate}"
            if gate_text not in failed_gates:
                failed_gates.append(gate_text)
        if report.get("status") not in {None, "", "pass"}:
            gate_text = f"{report_name}/{report.get('status')}"
            if gate_text not in failed_gates:
                failed_gates.append(gate_text)

    context = {
        "schema_version": 1,
        "paper_key": args.paper_key,
        "paths": {
            "source_pack": args.source_pack or "",
            "evidence_manifest": args.evidence_manifest or "",
            "copy_map": args.copy_map or "",
            "note": args.note or "",
            "quality_report": args.quality_report or "",
            "domain_report": args.domain_report or "",
            "validation_report": args.validation_report or "",
            "asset_report": args.asset_report or "",
        },
        "status": "pass" if not failed_gates and not failed_items else "needs_repair",
        "repair_scope": repair_scope(reports),
        "failed_gates": failed_gates,
        "failed_items": failed_items,
        "domain_conflict_fields": domain.get("conflict_fields", []),
        "instructions": [
            "Repair only this paper.",
            "Read only the listed source pack, evidence manifest, copy map, current note, and gate reports.",
            "After repair, rerun quality, domain, validation, asset, and unmatched-asset gates.",
        ],
    }
    output = json.dumps(context, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).expanduser().resolve().write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0 if context["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
