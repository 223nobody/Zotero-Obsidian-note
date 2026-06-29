#!/usr/bin/env python3
"""Create or update a per-paper JSON sidecar for batch note generation."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Maintain a resumable JSON sidecar for batch group-meeting notes."
    )
    parser.add_argument("--sidecar", required=True, help="Sidecar JSON path to create or update.")
    parser.add_argument("--paper-key", help="paper-search-mcp paper_key or local stable key.")
    parser.add_argument("--title", help="Readable paper title.")
    parser.add_argument("--pdf-path", help="Source PDF path.")
    parser.add_argument("--source-md", help="Readable source Markdown/full.md path.")
    parser.add_argument("--content-list", help="MinerU content_list.json path.")
    parser.add_argument("--assets-dir", help="Parser input assets directory.")
    parser.add_argument("--note-path", help="Final Obsidian/Zotero note path.")
    parser.add_argument("--manifest-path", help="Evidence manifest JSON path.")
    parser.add_argument("--copy-map-path", help="Manifest asset copy-map JSON path.")
    parser.add_argument("--asset-report-path", help="Asset audit JSON path.")
    parser.add_argument("--validation-report-path", help="validate_note.py JSON report path.")
    parser.add_argument("--quality-report-path", help="audit_note_quality.py JSON report path.")
    parser.add_argument(
        "--stage",
        choices=STAGES,
        help="Pipeline stage to mark.",
    )
    parser.add_argument(
        "--status",
        choices=["pending", "running", "complete", "failed", "skipped"],
        help="Stage status.",
    )
    parser.add_argument("--message", help="Optional status message.")
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Set an arbitrary top-level or dotted sidecar field, e.g. counts.used_images=12.",
    )
    return parser.parse_args()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig", errors="ignore"))


def load_sidecar(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "schema_version": 1,
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "paper_key": "",
            "title": "",
            "paths": {
                "pdf_path": "",
                "source_md": "",
                "content_list": "",
                "assets_dir": "",
                "note_path": "",
                "manifest_path": "",
                "copy_map_path": "",
                "asset_report_path": "",
                "validation_report_path": "",
                "quality_report_path": "",
            },
            "stages": {
                stage: {"status": "pending", "updated_at": "", "message": ""}
                for stage in STAGES
            },
            "counts": {},
            "used_images": [],
            "unused_images": [],
            "review_items": [],
            "validation": {},
            "quality": {},
            "errors": [],
        }
    return read_json(path)


def set_dotted(target: dict[str, Any], dotted_key: str, value: Any) -> None:
    current = target
    parts = dotted_key.split(".")
    for part in parts[:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    current[parts[-1]] = value


def parse_value(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def update_path(sidecar: dict[str, Any], key: str, value: str | None) -> None:
    if value is None:
        return
    sidecar.setdefault("paths", {})[key] = value


def main() -> int:
    args = parse_args()
    sidecar_path = Path(args.sidecar).expanduser().resolve()
    sidecar = load_sidecar(sidecar_path)
    sidecar["updated_at"] = now_iso()

    if args.paper_key is not None:
        sidecar["paper_key"] = args.paper_key
    if args.title is not None:
        sidecar["title"] = args.title

    update_path(sidecar, "pdf_path", args.pdf_path)
    update_path(sidecar, "source_md", args.source_md)
    update_path(sidecar, "content_list", args.content_list)
    update_path(sidecar, "assets_dir", args.assets_dir)
    update_path(sidecar, "note_path", args.note_path)
    update_path(sidecar, "manifest_path", args.manifest_path)
    update_path(sidecar, "copy_map_path", args.copy_map_path)
    update_path(sidecar, "asset_report_path", args.asset_report_path)
    update_path(sidecar, "validation_report_path", args.validation_report_path)
    update_path(sidecar, "quality_report_path", args.quality_report_path)

    if args.stage:
        status = args.status or "complete"
        sidecar.setdefault("stages", {}).setdefault(args.stage, {})
        sidecar["stages"][args.stage] = {
            "status": status,
            "updated_at": now_iso(),
            "message": args.message or "",
        }
        if status == "failed" and args.message:
            sidecar.setdefault("errors", []).append(
                {"stage": args.stage, "message": args.message, "updated_at": now_iso()}
            )

    for assignment in args.set:
        if "=" not in assignment:
            raise SystemExit(f"--set expects KEY=VALUE, got: {assignment}")
        key, value = assignment.split("=", 1)
        set_dotted(sidecar, key, parse_value(value))

    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    sidecar_path.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(sidecar, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
