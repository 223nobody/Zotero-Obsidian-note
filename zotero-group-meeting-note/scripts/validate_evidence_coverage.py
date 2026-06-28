#!/usr/bin/env python3
"""Validate final-note coverage against an evidence manifest."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
VALIDATE_NOTE = SCRIPT_DIR / "validate_note.py"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the evidence coverage gate for a generated note."
    )
    parser.add_argument("--note", required=True, help="Markdown note path.")
    parser.add_argument("--evidence-manifest", required=True, help="Evidence manifest JSON.")
    parser.add_argument("--copy-map", help="Optional prepare_output.py copy-map JSON.")
    parser.add_argument("--qa-report", help="Optional detailed QA JSON output path.")
    parser.add_argument("--strict", action="store_true", help="Fail on evidence warnings.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    command = [
        sys.executable,
        str(VALIDATE_NOTE),
        str(Path(args.note).expanduser().resolve()),
        "--evidence-manifest",
        str(Path(args.evidence_manifest).expanduser().resolve()),
        "--json",
    ]
    if args.copy_map:
        command.extend(["--copy-map", str(Path(args.copy_map).expanduser().resolve())])
    if args.qa_report:
        command.extend(["--qa-report", str(Path(args.qa_report).expanduser().resolve())])
    if args.strict:
        command.append("--strict-evidence")

    result = subprocess.run(command, text=True, capture_output=True, encoding="utf-8")
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        payload = {
            "status": "fail",
            "errors": [{"kind": "invalid_validate_note_output", "line": 0, "message": result.stdout}],
            "warnings": [],
        }

    evidence_kinds = {
        "missing_copy_map_entry",
        "missing_required_evidence",
        "missing_evidence_reference",
        "missing_evidence_asset_link",
        "misplaced_evidence_asset_link",
        "evidence_order_error",
    }
    evidence_errors = [
        item for item in payload.get("errors", []) if item.get("kind") in evidence_kinds
    ]
    evidence_warnings = [
        item for item in payload.get("warnings", []) if item.get("kind") in evidence_kinds
    ]
    report = {
        "note": payload.get("note", str(Path(args.note).expanduser().resolve())),
        "manifest": str(Path(args.evidence_manifest).expanduser().resolve()),
        "status": "pass" if not evidence_errors and not (args.strict and evidence_warnings) else "fail",
        "errors": evidence_errors,
        "warnings": evidence_warnings,
        "all_validation_status": payload.get("status", ""),
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"# Evidence Coverage\n\nStatus: {report['status']}")
        for key in ("errors", "warnings"):
            print(f"\n## {key.title()}")
            rows = report[key]
            if not rows:
                print("- <none>")
            for row in rows:
                print(f"- line {row.get('line', 0)}: [{row.get('kind')}] {row.get('message')}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
