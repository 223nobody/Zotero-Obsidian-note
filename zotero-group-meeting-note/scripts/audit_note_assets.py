#!/usr/bin/env python3
"""Audit and optionally clean note-local assets without writing into the note body."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote


IMAGE_RE = re.compile(r"!\[[^\]]*\]\((?P<target>[^)]+)\)")
WIKI_IMAGE_RE = re.compile(
    r"!\[\[(?P<target>[^\]|#]+)(?:#[^\]|]+)?(?:\|(?P<alt>[^\]]+))?\]\]"
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report note image usage, unused assets, and duplicate asset hashes."
    )
    parser.add_argument("note", help="Markdown note path.")
    parser.add_argument(
        "--assets-dir",
        help="Assets directory. Defaults to <note parent>/assets.",
    )
    parser.add_argument(
        "--output",
        help="Write JSON report to this path. Defaults to stdout.",
    )
    parser.add_argument(
        "--delete-unused",
        action="store_true",
        help="Delete files under assets_dir that are not referenced by the note.",
    )
    parser.add_argument(
        "--delete-duplicate-unused",
        action="store_true",
        help="Delete only unused files whose SHA256 duplicates a referenced file.",
    )
    parser.add_argument(
        "--scan-sibling-notes",
        action="store_true",
        help="Also scan other Markdown notes in the same folder before classifying assets as unused.",
    )
    parser.add_argument(
        "--recursive-sibling-notes",
        action="store_true",
        help="When scanning sibling notes, include Markdown files recursively under the note folder.",
    )
    parser.add_argument(
        "--recursive-assets",
        action="store_true",
        help="Scan files recursively under assets_dir instead of only immediate files.",
    )
    parser.add_argument(
        "--vault-root",
        help="Optional Obsidian vault root used to resolve wiki embeds.",
    )
    return parser.parse_args()


def clean_target(target: str) -> str:
    value = target.strip().strip("<>")
    value = value.split("#", 1)[0].split("?", 1)[0]
    return unquote(value).replace("\\", "/")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_wiki_target(note_path: Path, target: str, vault_root: Path | None = None) -> tuple[str, bool]:
    clean = clean_target(target)
    candidates: list[Path] = []
    raw_path = Path(clean)
    if raw_path.is_absolute():
        candidates.append(raw_path)
    else:
        candidates.append(note_path.parent / raw_path)
        if vault_root:
            candidates.append(vault_root / raw_path)
            if len(raw_path.parts) == 1:
                candidates.extend(sorted(vault_root.rglob(raw_path.name)))
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if resolved.is_file():
            return str(resolved), True
    fallback = (note_path.parent / raw_path).resolve()
    return str(fallback), False


def collect_note_links(
    note_path: Path, text: str, vault_root: Path | None = None
) -> list[dict[str, str | bool]]:
    links: list[dict[str, str | bool]] = []
    for match in IMAGE_RE.finditer(text):
        raw_target = match.group("target")
        target = clean_target(raw_target)
        if re.match(r"^(?:https?|data):", target, re.IGNORECASE):
            resolved = ""
            exists = False
        else:
            path = Path(target)
            resolved_path = path if path.is_absolute() else note_path.parent / path
            resolved = str(resolved_path.resolve())
            exists = resolved_path.is_file()
        links.append(
            {
                "target": target,
                "resolved_path": resolved,
                "exists": exists,
                "syntax": "markdown",
            }
        )
    for match in WIKI_IMAGE_RE.finditer(text):
        target = clean_target(match.group("target"))
        resolved, exists = resolve_wiki_target(note_path, target, vault_root)
        links.append(
            {
                "target": target,
                "resolved_path": resolved,
                "exists": exists,
                "syntax": "wiki",
            }
        )
    return links


def sibling_referenced_paths(
    note_path: Path,
    assets_dir: Path,
    vault_root: Path | None = None,
    recursive_sibling_notes: bool = False,
) -> set[str]:
    referenced: set[str] = set()
    pattern = "**/*.md" if recursive_sibling_notes else "*.md"
    for sibling in sorted(note_path.parent.glob(pattern)):
        if sibling.resolve() == note_path.resolve():
            continue
        text = sibling.read_text(encoding="utf-8-sig", errors="ignore")
        for link in collect_note_links(sibling, text, vault_root):
            resolved = str(link.get("resolved_path") or "")
            if link.get("exists") and resolved:
                try:
                    Path(resolved).resolve().relative_to(assets_dir.resolve())
                except ValueError:
                    continue
                referenced.add(str(Path(resolved).resolve()))
    return referenced


def build_report(
    note_path: Path,
    assets_dir: Path,
    scan_sibling_notes: bool = False,
    recursive_sibling_notes: bool = False,
    recursive_assets: bool = False,
    vault_root: Path | None = None,
) -> dict[str, object]:
    text = note_path.read_text(encoding="utf-8", errors="ignore")
    links = collect_note_links(note_path, text, vault_root)
    referenced_paths = {
        str(Path(str(link["resolved_path"])).resolve())
        for link in links
        if link.get("resolved_path") and link.get("exists")
    }
    sibling_paths = (
        sibling_referenced_paths(note_path, assets_dir, vault_root, recursive_sibling_notes)
        if scan_sibling_notes
        else set()
    )

    asset_iter = assets_dir.rglob("*") if recursive_assets else assets_dir.glob("*")
    asset_files = sorted(path for path in asset_iter if path.is_file()) if assets_dir.is_dir() else []
    file_records: list[dict[str, object]] = []
    hash_groups: dict[str, list[str]] = {}
    for path in asset_files:
        file_hash = sha256(path)
        resolved = str(path.resolve())
        hash_groups.setdefault(file_hash, []).append(resolved)
        file_records.append(
            {
                "path": resolved,
                "name": path.name,
                "bytes": path.stat().st_size,
                "sha256": file_hash,
                "referenced": resolved in referenced_paths,
                "referenced_by_sibling_note": resolved in sibling_paths,
            }
        )

    duplicate_groups = [
        {"sha256": file_hash, "paths": paths}
        for file_hash, paths in sorted(hash_groups.items())
        if len(paths) > 1
    ]
    unused_assets = [
        record
        for record in file_records
        if not record["referenced"] and not record["referenced_by_sibling_note"]
    ]
    sibling_referenced_assets = [
        record
        for record in file_records
        if not record["referenced"] and record["referenced_by_sibling_note"]
    ]
    referenced_hashes = {
        str(record["sha256"])
        for record in file_records
        if record["referenced"]
    }
    duplicate_unused_assets = [
        record
        for record in unused_assets
        if str(record["sha256"]) in referenced_hashes
    ]

    return {
        "note": str(note_path),
        "assets_dir": str(assets_dir),
        "image_link_count": len(links),
        "wiki_image_link_count": sum(1 for link in links if link.get("syntax") == "wiki"),
        "markdown_image_link_count": sum(1 for link in links if link.get("syntax") == "markdown"),
        "resolved_image_link_count": sum(1 for link in links if link.get("exists")),
        "assets_total": len(file_records),
        "referenced_assets_count": sum(1 for record in file_records if record["referenced"]),
        "sibling_referenced_assets_count": len(sibling_referenced_assets),
        "unused_assets_count": len(unused_assets),
        "duplicate_hash_count": len(duplicate_groups),
        "duplicate_file_count": sum(len(group["paths"]) for group in duplicate_groups),
        "image_links": links,
        "assets": file_records,
        "unused_assets": unused_assets,
        "sibling_referenced_assets": sibling_referenced_assets,
        "duplicate_unused_assets": duplicate_unused_assets,
        "duplicate_groups": duplicate_groups,
    }


def delete_paths(paths: list[str], assets_dir: Path) -> tuple[list[str], list[str]]:
    deleted: list[str] = []
    skipped: list[str] = []
    assets_root = assets_dir.resolve()
    for raw_path in paths:
        path = Path(raw_path).expanduser().resolve()
        try:
            path.relative_to(assets_root)
        except ValueError:
            skipped.append(str(path))
            continue
        if path.is_file():
            path.unlink()
            deleted.append(str(path))
    return deleted, skipped


def main() -> int:
    args = parse_args()
    note_path = Path(args.note).expanduser().resolve()
    assets_dir = (
        Path(args.assets_dir).expanduser().resolve()
        if args.assets_dir
        else (note_path.parent / "assets").resolve()
    )
    vault_root = Path(args.vault_root).expanduser().resolve() if args.vault_root else None
    report = build_report(
        note_path,
        assets_dir,
        scan_sibling_notes=args.scan_sibling_notes,
        recursive_sibling_notes=args.recursive_sibling_notes,
        recursive_assets=args.recursive_assets,
        vault_root=vault_root,
    )

    to_delete: list[str] = []
    if args.delete_unused:
        to_delete = [str(record["path"]) for record in report["unused_assets"]]  # type: ignore[index]
    elif args.delete_duplicate_unused:
        to_delete = [str(record["path"]) for record in report["duplicate_unused_assets"]]  # type: ignore[index]
    deleted, skipped_delete_paths = delete_paths(to_delete, assets_dir)
    if deleted:
        report = build_report(
            note_path,
            assets_dir,
            scan_sibling_notes=args.scan_sibling_notes,
            recursive_sibling_notes=args.recursive_sibling_notes,
            recursive_assets=args.recursive_assets,
            vault_root=vault_root,
        )
        report["deleted_assets"] = deleted
    else:
        report["deleted_assets"] = []
    report["skipped_delete_paths"] = skipped_delete_paths

    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).expanduser().resolve().write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
