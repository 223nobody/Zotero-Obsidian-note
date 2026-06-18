#!/usr/bin/env python3
"""Copy local Markdown image assets into an Obsidian-style assets folder."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse


IMAGE_RE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<target>[^)]+)\)")
WIKI_IMAGE_RE = re.compile(
    r"!\[\[(?P<target>[^\]|#]+)(?:#[^\]|]+)?(?:\|(?P<alt>[^\]]+))?\]\]"
)
INVALID_WINDOWS_CHARS = '<>:"/\\|?*'

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect local images referenced by Markdown into an assets folder."
    )
    parser.add_argument("markdown", help="Markdown file whose image links should be scanned.")
    parser.add_argument(
        "--assets-dir",
        required=True,
        help="Destination assets directory, usually beside the Obsidian note.",
    )
    parser.add_argument(
        "--rewrite-markdown",
        help="Optional output path for Markdown with image links rewritten to assets/<file>.",
    )
    parser.add_argument(
        "--vault-root",
        help="Optional Obsidian vault root used to resolve wiki image embeds such as ![[Pasted image.png]].",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON only.")
    return parser.parse_args()


def sanitize_filename(value: str, max_chars: int = 90) -> str:
    cleaned = "".join("-" if char in INVALID_WINDOWS_CHARS else char for char in value)
    cleaned = " ".join(cleaned.split()).strip(" .")
    cleaned = cleaned or "asset"
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars].rstrip()


def is_remote(target: str) -> bool:
    parsed = urlparse(target)
    return parsed.scheme in {"http", "https", "data"}


def resolve_image_path(
    markdown_path: Path, target: str, vault_root: Path | None = None
) -> Path | None:
    if is_remote(target):
        return None
    target = target.strip().strip("<>")
    if "#" in target:
        target = target.split("#", 1)[0]
    if "?" in target:
        target = target.split("?", 1)[0]
    target = unquote(target)
    path = Path(target)
    if not path.is_absolute():
        path = markdown_path.parent / path
    path = path.expanduser().resolve()
    if path.is_file():
        return path

    if vault_root:
        wiki_target = Path(target)
        direct = (vault_root / wiki_target).expanduser().resolve()
        if direct.is_file():
            return direct
        if len(wiki_target.parts) == 1:
            matches = sorted(vault_root.rglob(wiki_target.name))
            for match in matches:
                if match.is_file():
                    return match.resolve()
    return None


def unique_destination(path: Path) -> Path:
    if not path.exists():
        return path
    parent = path.parent
    stem = path.stem
    suffix = path.suffix
    counter = 2
    while True:
        candidate = parent / f"{stem}-{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def existing_asset_by_hash(assets_dir: Path, source_hash: str, preferred_stem: str) -> Path | None:
    if not source_hash or not assets_dir.is_dir():
        return None
    for candidate in sorted(assets_dir.iterdir()):
        if not candidate.is_file():
            continue
        if candidate.stem != preferred_stem and not candidate.stem.startswith(f"{preferred_stem}-"):
            continue
        try:
            if file_sha256(candidate) == source_hash:
                return candidate
        except OSError:
            continue
    return None


def copy_image(source: Path, assets_dir: Path) -> Path:
    safe_stem = sanitize_filename(source.stem)
    suffix = source.suffix.lower() or ".png"
    existing = existing_asset_by_hash(assets_dir, file_sha256(source), safe_stem)
    if existing:
        return existing
    destination = unique_destination(assets_dir / f"{safe_stem}{suffix}")
    shutil.copy2(source, destination)
    return destination


def main() -> int:
    args = parse_args()
    markdown_path = Path(args.markdown).expanduser().resolve()
    assets_dir = Path(args.assets_dir).expanduser().resolve()
    vault_root = Path(args.vault_root).expanduser().resolve() if args.vault_root else None
    assets_dir.mkdir(parents=True, exist_ok=True)

    text = markdown_path.read_text(encoding="utf-8", errors="ignore")
    replacements: dict[str, str] = {}
    wiki_replacements: dict[str, str] = {}
    copied: list[dict[str, str]] = []
    missing: list[dict[str, str]] = []

    for match in IMAGE_RE.finditer(text):
        original = match.group("target")
        if original in replacements:
            continue
        source = resolve_image_path(markdown_path, original, vault_root)
        if source is None:
            missing.append({"target": original, "reason": "remote_or_missing"})
            continue
        destination = copy_image(source, assets_dir)
        relative = f"assets/{destination.name}"
        replacements[original] = relative
        copied.append(
            {
                "source": str(source),
                "destination": str(destination),
                "markdown": relative,
            }
        )

    for match in WIKI_IMAGE_RE.finditer(text):
        original_embed = match.group(0)
        original_target = match.group("target").strip()
        if original_embed in wiki_replacements:
            continue
        source = resolve_image_path(markdown_path, original_target, vault_root)
        if source is None:
            missing.append({"target": original_target, "reason": "wiki_remote_or_missing"})
            continue
        destination = copy_image(source, assets_dir)
        relative = f"assets/{destination.name}"
        alt = (match.group("alt") or source.stem).strip()
        wiki_replacements[original_embed] = f"![{alt}]({relative})"
        copied.append(
            {
                "source": str(source),
                "destination": str(destination),
                "markdown": relative,
            }
        )

    rewritten_text = text
    for original, replacement in replacements.items():
        rewritten_text = rewritten_text.replace(f"]({original})", f"]({replacement})")
    for original, replacement in wiki_replacements.items():
        rewritten_text = rewritten_text.replace(original, replacement)

    if args.rewrite_markdown:
        output_path = Path(args.rewrite_markdown).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rewritten_text, encoding="utf-8")
    else:
        output_path = None

    result = {
        "markdown": str(markdown_path),
        "assets_dir": str(assets_dir),
        "copied": copied,
        "missing": missing,
        "rewrite_markdown": str(output_path) if output_path else None,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("# Collected Assets")
        print()
        print(f"Copied: {len(copied)}")
        print(f"Missing or remote: {len(missing)}")
        if output_path:
            print(f"Rewritten Markdown: {output_path}")
        for item in copied:
            print(f"- {item['markdown']} <- {item['source']}")
        for item in missing:
            print(f"- missing/remote: {item['target']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
