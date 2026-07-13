#!/usr/bin/env python3
"""Audit MinerU source assets that did not make it into a final note asset folder."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
ASSET_KEY_RE = re.compile(
    r"(^|_)(?:path|paths|img|image|asset|figure|formula|table)(?:$|_)",
    re.IGNORECASE,
)
NON_ASSET_KEY_RE = re.compile(r"(?:body|html|text|caption|content|latex|title|alt|code)", re.IGNORECASE)
TYPE_KEY_RE = re.compile(r"(?:type|category|block_type)", re.IGNORECASE)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare MinerU source assets with final note assets and classify missing files."
    )
    parser.add_argument("--content-list", help="MinerU content_list.json path.")
    parser.add_argument(
        "--source-assets-dir",
        required=True,
        help="MinerU assets directory or a subdirectory such as assets/figures.",
    )
    parser.add_argument("--note-assets-dir", help="Final Obsidian note assets directory.")
    parser.add_argument("--evidence-manifest", help="Optional evidence manifest JSON.")
    parser.add_argument("--output", help="Write JSON report to this path. Defaults to stdout.")
    parser.add_argument(
        "--fail-on-problem-assets",
        action="store_true",
        help="Exit non-zero when formula or structured source assets are missing from final assets.",
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig", errors="ignore"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        with path.open("rb") as handle:
            header = handle.read(32)
            if header.startswith(b"\x89PNG\r\n\x1a\n") and len(header) >= 24:
                return int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")
            if header[:3] == b"GIF" and len(header) >= 10:
                return int.from_bytes(header[6:8], "little"), int.from_bytes(header[8:10], "little")
            if header.startswith(b"\xff\xd8"):
                handle.seek(2)
                while True:
                    prefix = handle.read(1)
                    if not prefix:
                        return None
                    if prefix != b"\xff":
                        continue
                    marker = handle.read(1)
                    while marker == b"\xff":
                        marker = handle.read(1)
                    if not marker:
                        return None
                    value = marker[0]
                    if value in {0xD8, 0xD9}:
                        continue
                    length_bytes = handle.read(2)
                    if len(length_bytes) != 2:
                        return None
                    segment_length = int.from_bytes(length_bytes, "big")
                    if value in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                        data = handle.read(5)
                        if len(data) != 5:
                            return None
                        return int.from_bytes(data[3:5], "big"), int.from_bytes(data[1:3], "big")
                    handle.seek(max(0, segment_length - 2), 1)
    except OSError:
        return None
    return None


def is_likely_formula_image(path: Path) -> bool:
    lowered = path.as_posix().lower()
    if any(token in lowered for token in ("equation", "formula", "latex", "loss", "objective")):
        return True
    dims = image_dimensions(path)
    if not dims:
        return False
    width, height = dims
    if height <= 0:
        return False
    ratio = width / height
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    return height <= 140 and width >= 120 and ratio >= 2.0 and size <= 25000


def image_files(root: Path | None) -> list[Path]:
    if not root or not root.is_dir():
        return []
    return sorted(
        path.resolve()
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def walk_strings(value: Any, key_hint: str = "") -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            result.extend(walk_strings(item, str(key)))
    elif isinstance(value, list):
        for item in value:
            result.extend(walk_strings(item, key_hint))
    elif isinstance(value, (str, int, float)):
        result.append((key_hint, str(value)))
    return result


def block_type(block: dict[str, Any]) -> str:
    for key, value in block.items():
        if TYPE_KEY_RE.search(str(key)):
            return str(value)
    return ""


def resolve_asset(raw: str, source_assets_dir: Path) -> Path | None:
    clean = raw.strip().strip("<>").split("#", 1)[0].split("?", 1)[0].replace("\\", "/")
    path = Path(clean)
    if path.is_absolute():
        return path.resolve() if path.is_file() else None
    candidates = [
        source_assets_dir / clean,
        source_assets_dir / path.name,
        source_assets_dir / "figures" / path.name,
        source_assets_dir / "tables" / path.name,
        source_assets_dir / "equations" / path.name,
        source_assets_dir / "images" / path.name,
        source_assets_dir.parent / clean,
        source_assets_dir.parent / "figures" / path.name,
        source_assets_dir.parent / "tables" / path.name,
        source_assets_dir.parent / "equations" / path.name,
        source_assets_dir.parent / "images" / path.name,
    ]
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved
    return None


def content_list_asset_index(content_list_path: Path | None, source_assets_dir: Path) -> dict[str, dict[str, Any]]:
    if not content_list_path or not content_list_path.is_file():
        return {}
    data = read_json(content_list_path)
    blocks = data if isinstance(data, list) else data.get("content_list") or data.get("blocks") if isinstance(data, dict) else []
    if not isinstance(blocks, list):
        blocks = [data] if isinstance(data, dict) else []
    index: dict[str, dict[str, Any]] = {}
    for block_index, block in enumerate(blocks, start=1):
        if not isinstance(block, dict):
            continue
        btype = block_type(block)
        for key, value in walk_strings(block):
            if NON_ASSET_KEY_RE.search(key):
                continue
            raw = value.strip()
            suffix = Path(raw.split("#", 1)[0].split("?", 1)[0]).suffix.lower()
            if suffix not in IMAGE_EXTENSIONS and not ASSET_KEY_RE.search(key):
                continue
            resolved = resolve_asset(raw, source_assets_dir)
            if not resolved:
                continue
            file_hash = sha256(resolved)
            index[file_hash] = {
                "content_list_block_index": block_index,
                "content_list_type": btype,
                "content_list_key": key,
                "content_list_raw_path": raw,
                "content_list_resolved_path": str(resolved),
            }
    return index


def manifest_hashes(manifest_path: Path | None) -> set[str]:
    if not manifest_path or not manifest_path.is_file():
        return set()
    data = read_json(manifest_path)
    items = data.get("items") if isinstance(data, dict) else []
    if isinstance(data, dict) and "items" not in data:
        items = list(data.get("main_items", [])) + list(data.get("post_reference_items", []))
    hashes: set[str] = set()
    if not isinstance(items, list):
        return hashes
    for item in items:
        if not isinstance(item, dict):
            continue
        asset_hashes = item.get("asset_hashes")
        if isinstance(asset_hashes, dict):
            hashes.update(str(value) for value in asset_hashes.values() if value)
        for asset in item.get("canonical_assets", []) if isinstance(item.get("canonical_assets"), list) else []:
            if isinstance(asset, dict) and asset.get("sha256"):
                hashes.add(str(asset["sha256"]))
    return hashes


def classify_missing(path: Path, file_hash: str, content_index: dict[str, dict[str, Any]], manifest_seen: set[str]) -> str:
    if file_hash in manifest_seen:
        return "manifest_matched_missing_from_final"
    if file_hash in content_index:
        btype = str(content_index[file_hash].get("content_list_type", "")).lower()
        if any(token in btype for token in ("image", "chart", "figure")):
            return "structured_figure_or_panel_missing"
        if "table" in btype:
            return "structured_table_missing"
        if "equation" in btype or "formula" in btype:
            return "structured_formula_missing"
        return "structured_asset_missing"
    if is_likely_formula_image(path):
        return "formula_orphan_missing"
    return "likely_noise_or_unmatched_crop"


def build_report(
    source_assets_dir: Path,
    note_assets_dir: Path | None,
    content_list_path: Path | None,
    evidence_manifest_path: Path | None,
) -> dict[str, Any]:
    source_files = image_files(source_assets_dir)
    final_hashes = {sha256(path) for path in image_files(note_assets_dir)} if note_assets_dir else set()
    content_index = content_list_asset_index(content_list_path, source_assets_dir)
    manifest_seen = manifest_hashes(evidence_manifest_path)
    missing: list[dict[str, Any]] = []
    for path in source_files:
        file_hash = sha256(path)
        if file_hash in final_hashes:
            continue
        classification = classify_missing(path, file_hash, content_index, manifest_seen)
        dims = image_dimensions(path)
        missing.append(
            {
                "source_path": str(path),
                "name": path.name,
                "sha256": file_hash,
                "bytes": path.stat().st_size,
                "dimensions": {"width": dims[0], "height": dims[1]} if dims else {},
                "classification": classification,
                "content_list": content_index.get(file_hash, {}),
            }
        )
    problem_classes = {
        "formula_orphan_missing",
        "structured_figure_or_panel_missing",
        "structured_table_missing",
        "structured_formula_missing",
        "manifest_matched_missing_from_final",
    }
    problems = [item for item in missing if item["classification"] in problem_classes]
    failed_gates = ["unmatched_problem_assets"] if problems else []
    return {
        "schema_version": 2,
        "report_type": "unmatched_asset",
        "status": "fail" if failed_gates else "pass",
        "ok": not failed_gates,
        "source_assets_dir": str(source_assets_dir),
        "note_assets_dir": str(note_assets_dir) if note_assets_dir else "",
        "content_list": str(content_list_path) if content_list_path else "",
        "evidence_manifest": str(evidence_manifest_path) if evidence_manifest_path else "",
        "source_asset_count": len(source_files),
        "note_asset_hash_count": len(final_hashes),
        "missing_count": len(missing),
        "problem_count": len(problems),
        "classification_counts": {
            key: sum(1 for item in missing if item["classification"] == key)
            for key in sorted({item["classification"] for item in missing})
        },
        "missing_assets": missing,
        "problem_assets": problems,
        "failed_gates": failed_gates,
    }


def main() -> int:
    args = parse_args()
    source_assets_dir = Path(args.source_assets_dir).expanduser().resolve()
    note_assets_dir = Path(args.note_assets_dir).expanduser().resolve() if args.note_assets_dir else None
    content_list_path = Path(args.content_list).expanduser().resolve() if args.content_list else None
    evidence_manifest_path = (
        Path(args.evidence_manifest).expanduser().resolve() if args.evidence_manifest else None
    )
    report = build_report(source_assets_dir, note_assets_dir, content_list_path, evidence_manifest_path)
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    if args.fail_on_problem_assets and report["problem_count"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
