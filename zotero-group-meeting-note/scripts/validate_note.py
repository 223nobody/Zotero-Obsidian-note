#!/usr/bin/env python3
"""Validate structural output rules for generated group-meeting notes."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse
from typing import Any


BANNED_PATTERNS = [
    ("mineru_asset_index", re.compile(r"附录[:：]?\s*MinerU\s*图片资源完整性索引", re.IGNORECASE)),
    ("resource_completeness_index", re.compile(r"图片资源完整性索引|资源完整性索引")),
    ("mineru_asset_label", re.compile(r"MinerU\s+asset", re.IGNORECASE)),
    ("mineru_extra_crop", re.compile(r"MinerU\s+extra\s+crop", re.IGNORECASE)),
]
IMAGE_RE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<target>[^)]+)\)")
WIKI_IMAGE_RE = re.compile(r"!\[\[(?P<target>[^\]|#]+)(?:#[^\]|]+)?(?:\|(?P<alt>[^\]]+))?\]\]")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(?P<title>.+?)\s*$", re.MULTILINE)
ASSET_ONLY_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:!\[[^\]]*\]\()?assets[\\/][^) \t]+(?:\))?\s*$",
    re.IGNORECASE,
)
ABSOLUTE_LOCAL_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|/|\\\\)")
EVIDENCE_ENTRY_RE = re.compile(
    r"^\s*(?:[-*+]\s*)?(?:\|+\s*)?(?:\*\*)?\s*"
    r"(?:Figure|Fig\.|Table|Equation|Eq\.|Algorithm|Alg\.|Objective|Loss|Score|"
    r"Constraint|Prompt|Case Study|Checklist)\s*[A-Za-z]?\d*",
    re.IGNORECASE,
)
EVIDENCE_SECTION_RE = re.compile(
    r"(figure|table|equation|evidence|appendix|supplement|图|表|公式|证据|补充|附录)",
    re.IGNORECASE,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check generated note assets and banned MinerU audit sections."
    )
    parser.add_argument("note", help="Markdown note to validate.")
    parser.add_argument(
        "--assets-dir",
        help="Assets directory. Defaults to <note parent>/assets.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown.")
    parser.add_argument(
        "--allow-wiki",
        action="store_true",
        help="Allow Obsidian wiki image embeds. Default is to report them as errors.",
    )
    parser.add_argument(
        "--evidence-manifest",
        help="Optional evidence manifest JSON from build_evidence_manifest.py. "
        "When provided, checks that high-confidence main-region evidence items "
        "with matched assets are referenced in the note body.",
    )
    parser.add_argument(
        "--copy-map",
        help="Optional copy-map JSON from prepare_output.py --copy-map. "
        "Used to verify manifest assets by copied destination/hash instead of basename only.",
    )
    parser.add_argument(
        "--strict-evidence",
        action="store_true",
        help="Treat evidence placement warnings as validation errors.",
    )
    parser.add_argument(
        "--blueprint",
        help="Optional references/blueprint.md path used as the structure contract.",
    )
    parser.add_argument(
        "--strict-assets",
        action="store_true",
        help="Treat non-assets relative image links and remote images as validation errors.",
    )
    parser.add_argument(
        "--copy-map-authoritative",
        action="store_true",
        help="When --copy-map is provided, accept only copy-map destination/hash/markdown links for evidence assets.",
    )
    parser.add_argument(
        "--qa-report",
        help="Optional JSON path for evidence/image placement QA details.",
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig", errors="ignore"))


def is_remote(target: str) -> bool:
    parsed = urlparse(target)
    return parsed.scheme in {"http", "https", "data"}


def clean_target(target: str) -> str:
    value = target.strip().strip("<>")
    value = value.split("#", 1)[0].split("?", 1)[0]
    return unquote(value)


def resolve_relative(note_path: Path, target: str) -> Path:
    target_path = Path(clean_target(target).replace("\\", "/"))
    if target_path.is_absolute():
        return target_path
    return (note_path.parent / target_path).resolve()


def iter_manifest_items(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if "items" in manifest:
        return list(manifest.get("items", []))
    return list(manifest.get("main_items", [])) + list(manifest.get("post_reference_items", []))


def note_image_targets(note_path: Path, text: str) -> set[str]:
    targets: set[str] = set()
    for match in IMAGE_RE.finditer(text):
        target = clean_target(match.group("target")).replace("\\", "/")
        targets.add(target)
        if not is_remote(target):
            targets.add(str(resolve_relative(note_path, target)))
            targets.add(Path(target).name)
    return targets


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_records(note_path: Path, text: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for match in IMAGE_RE.finditer(text):
        raw_target = match.group("target")
        target = clean_target(raw_target).replace("\\", "/")
        line = text.count("\n", 0, match.start()) + 1
        resolved = None if is_remote(target) else resolve_relative(note_path, target)
        records.append(
            {
                "target": target,
                "basename": Path(target).name,
                "line": line,
                "start": match.start(),
                "end": match.end(),
                "resolved_path": str(resolved) if resolved else "",
                "sha256": file_sha256(resolved) if resolved and resolved.is_file() else "",
            }
        )
    return records


def heading_spans(note_text: str) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    matches = list(HEADING_RE.finditer(note_text))
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(note_text)
        spans.append(
            {
                "title": match.group("title"),
                "line": note_text.count("\n", 0, start) + 1,
                "start": start,
                "end": end,
            }
        )
    return spans


def line_spans(note_text: str) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    start = 0
    for line_no, line in enumerate(note_text.splitlines(keepends=True), start=1):
        end = start + len(line)
        spans.append(
            {
                "line": line_no,
                "text": line.rstrip("\r\n"),
                "start": start,
                "end": end,
            }
        )
        start = end
    if not spans and note_text:
        spans.append({"line": 1, "text": note_text, "start": 0, "end": len(note_text)})
    return spans


def label_pattern(label: str) -> re.Pattern[str]:
    parts = [re.escape(part) for part in re.split(r"\s+", label.strip()) if part]
    return re.compile(r"\b" + r"\s*[:：.\-]?\s*".join(parts) + r"\b", re.IGNORECASE)


def normalized_entry_line(line: str) -> str:
    value = line.strip()
    value = re.sub(r"^\s*(?:[-*+]\s*)?(?:\|+\s*)?", "", value)
    value = value.strip()
    value = re.sub(r"^\*\*", "", value).strip()
    return value


def is_evidence_section_span(spans: list[dict[str, Any]], position: int) -> bool:
    current = None
    for span in spans:
        if span["start"] <= position:
            current = span
        else:
            break
    return bool(current and EVIDENCE_SECTION_RE.search(str(current.get("title", ""))))


def next_window_end(
    note_text: str,
    lines: list[dict[str, Any]],
    current_index: int,
    heading_starts: set[int],
) -> int:
    for next_line in lines[current_index + 1 :]:
        if next_line["start"] in heading_starts:
            return int(next_line["start"])
        if EVIDENCE_ENTRY_RE.match(normalized_entry_line(str(next_line["text"]))):
            return int(next_line["start"])
    return len(note_text)


def evidence_window(note_text: str, label: str) -> dict[str, Any] | None:
    spans = heading_spans(note_text)
    lines = line_spans(note_text)
    pattern = label_pattern(label)
    heading_starts = {int(span["start"]) for span in spans}
    candidates: list[dict[str, Any]] = []

    for span in spans:
        if pattern.search(str(span["title"])):
            score = 120
            if is_evidence_section_span(spans, int(span["start"])):
                score += 20
            candidates.append({**span, "score": score, "match_kind": "heading"})

    for index, line in enumerate(lines):
        text = str(line["text"])
        if not pattern.search(text):
            continue
        normalized = normalized_entry_line(text)
        is_heading = int(line["start"]) in heading_starts
        is_entry = bool(EVIDENCE_ENTRY_RE.match(normalized))
        has_image = bool(IMAGE_RE.search(text))
        if is_heading:
            score = 120
        elif is_entry:
            score = 95
        elif has_image:
            score = 55
        else:
            score = 10
        if is_evidence_section_span(spans, int(line["start"])):
            score += 20
        if not is_entry and not is_heading and not has_image:
            score -= 5
        start = int(line["start"])
        end = next_window_end(note_text, lines, index, heading_starts) if is_entry or has_image else int(line["end"])
        candidates.append(
            {
                "title": label,
                "line": int(line["line"]),
                "start": start,
                "end": end,
                "score": score,
                "match_kind": "entry" if is_entry else "image" if has_image else "mention",
            }
        )

    if not candidates:
        return None
    candidates.sort(key=lambda item: (int(item["score"]), int(item["start"])), reverse=True)
    return candidates[0]


def copy_map_items_for_item(item: dict[str, Any], copy_map: dict[str, Any] | None) -> list[dict[str, str]]:
    copy_items: list[dict[str, str]] = []
    if not copy_map:
        return copy_items
    item_key = str(item.get("item_key", ""))
    grouped = copy_map.get("items", {})
    if item_key and isinstance(grouped, dict):
        copy_items.extend(grouped.get(item_key, []))
    if not copy_items:
        for copied in copy_map.get("copied_assets", []):
            if copied.get("label") == item.get("label"):
                copy_items.append(copied)
    return copy_items


def expected_assets_for_item(
    item: dict[str, Any],
    copy_map: dict[str, Any] | None,
    copy_map_authoritative: bool = False,
    allow_basename_fallback: bool = True,
) -> list[dict[str, str]]:
    expected: list[dict[str, str]] = []
    raw_asset_paths = item.get("asset_paths") or []
    if item.get("matched_asset"):
        raw_asset_paths = [item["matched_asset"]] + [
            path for path in raw_asset_paths if path != item["matched_asset"]
        ]
    copy_items = copy_map_items_for_item(item, copy_map)
    for copied in copy_items:
        expected.append(
            {
                "source": str(copied.get("source", "")),
                "source_sha256": str(copied.get("source_sha256", "")),
                "destination": str(copied.get("destination", "")),
                "destination_sha256": str(copied.get("destination_sha256", "")),
                "markdown": str(copied.get("markdown", "")),
                "basename": Path(str(copied.get("markdown") or copied.get("destination", ""))).name,
                "from_copy_map": "yes",
            }
        )
    if copy_map_authoritative and copy_map is not None:
        return expected
    for raw_asset in raw_asset_paths:
        path_text = str(raw_asset)
        if not path_text:
            continue
        expected.append(
            {
                "source": path_text,
                "source_sha256": str(item.get("asset_hashes", {}).get(path_text, "")),
                "destination": "",
                "destination_sha256": "",
                "markdown": "",
                "basename": Path(path_text.replace("\\", "/")).name,
                "allow_basename": "yes" if allow_basename_fallback else "no",
                "from_copy_map": "no",
            }
        )
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for asset in expected:
        key = (asset.get("markdown", ""), asset.get("destination", ""), asset.get("source", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(asset)
    return deduped


def asset_matches_record(expected: dict[str, str], record: dict[str, Any]) -> bool:
    markdown = expected.get("markdown", "").replace("\\", "/")
    destination = expected.get("destination", "")
    destination_hash = expected.get("destination_sha256", "")
    source_hash = expected.get("source_sha256", "")
    basename = expected.get("basename", "")
    source = expected.get("source", "")
    has_strong_identity = bool(markdown or destination or destination_hash or source_hash)
    if markdown and record.get("target") == markdown:
        return True
    if destination and record.get("resolved_path") == str(Path(destination).resolve()):
        return True
    if expected.get("from_copy_map") == "yes":
        if markdown or destination:
            return False
        return bool(destination_hash and record.get("sha256") == destination_hash)
    if source and expected.get("from_copy_map") != "yes":
        source_path = Path(source)
        if source_path.is_absolute() and record.get("resolved_path") == str(source_path.resolve()):
            return True
        source_normalized = source.replace("\\", "/")
        if not source_path.is_absolute() and (
            record.get("target") == source_normalized
            or record.get("target") == f"assets/{source_normalized}"
        ):
            return True
    if destination_hash and record.get("sha256") == destination_hash:
        return True
    if source_hash and record.get("sha256") == source_hash:
        return True
    if has_strong_identity:
        return False
    if expected.get("allow_basename") == "no":
        return False
    if basename and record.get("basename") == basename:
        return True
    return False


def check_banned_patterns(text: str) -> list[dict[str, str | int]]:
    errors: list[dict[str, str | int]] = []
    for key, pattern in BANNED_PATTERNS:
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            errors.append(
                {
                    "kind": key,
                    "line": line,
                    "message": f"Final note contains banned MinerU/resource-audit marker: {match.group(0)}",
                }
            )
    return errors


def check_asset_dump(lines: list[str]) -> list[dict[str, str | int]]:
    errors: list[dict[str, str | int]] = []
    consecutive_assets = 0
    consecutive_start = 0
    in_resource_like_section = False
    section_start = 0
    section_asset_count = 0

    for index, line in enumerate(lines, start=1):
        heading = HEADING_RE.match(line)
        if heading:
            title = heading.group("title").lower()
            in_resource_like_section = bool(
                re.search(r"mineru|资源|资产|asset|image|图片|索引|audit|manifest", title, re.IGNORECASE)
            )
            section_start = index
            section_asset_count = 0
            consecutive_assets = 0
            continue

        if ASSET_ONLY_RE.match(line):
            if consecutive_assets == 0:
                consecutive_start = index
            consecutive_assets += 1
            if in_resource_like_section:
                section_asset_count += 1
        elif line.strip():
            consecutive_assets = 0

        if consecutive_assets == 6:
            errors.append(
                {
                    "kind": "raw_asset_dump",
                    "line": consecutive_start,
                    "message": "Final note appears to contain a filename-only assets dump.",
                }
            )
        if in_resource_like_section and section_asset_count == 3:
            errors.append(
                {
                    "kind": "resource_section_asset_dump",
                    "line": section_start,
                    "message": "Resource-like section contains multiple bare asset links; move matched images to evidence entries or externalize the audit.",
                }
            )
    return errors


def check_image_links(
    note_path: Path, assets_dir: Path, text: str, allow_wiki: bool
) -> tuple[list[dict[str, str | int]], list[dict[str, str | int]], int]:
    errors: list[dict[str, str | int]] = []
    warnings: list[dict[str, str | int]] = []
    image_count = 0

    for match in IMAGE_RE.finditer(text):
        target = clean_target(match.group("target"))
        line = text.count("\n", 0, match.start()) + 1
        image_count += 1
        if is_remote(target):
            warnings.append(
                {
                    "kind": "remote_image",
                    "line": line,
                    "message": f"Remote image link should be copied locally when possible: {target}",
                }
            )
            continue
        if ABSOLUTE_LOCAL_RE.match(target):
            errors.append(
                {
                    "kind": "absolute_image_path",
                    "line": line,
                    "message": f"Use note-local relative assets/... path instead of absolute image path: {target}",
                }
            )
            continue
        if not target.replace("\\", "/").startswith("assets/"):
            warnings.append(
                {
                    "kind": "non_assets_relative_image",
                    "line": line,
                    "message": f"Image link is relative but not under note-local assets/: {target}",
                }
            )
        resolved = resolve_relative(note_path, target)
        if not resolved.is_file():
            errors.append(
                {
                    "kind": "missing_image_file",
                    "line": line,
                    "message": f"Image link does not resolve to a file: {target}",
                }
            )
        elif target.replace("\\", "/").startswith("assets/"):
            try:
                resolved.relative_to(assets_dir.resolve())
            except ValueError:
                errors.append(
                    {
                        "kind": "image_outside_assets_dir",
                        "line": line,
                        "message": f"assets/ link resolves outside the configured assets dir: {target}",
                    }
                )

    for match in WIKI_IMAGE_RE.finditer(text):
        target = match.group("target")
        line = text.count("\n", 0, match.start()) + 1
        if allow_wiki:
            warnings.append(
                {
                    "kind": "wiki_image_embed",
                    "line": line,
                    "message": f"Wiki image embed remains in note: {target}",
                }
            )
        else:
            errors.append(
                {
                    "kind": "wiki_image_embed",
                    "line": line,
                    "message": f"Rewrite wiki image embed to note-local Markdown asset link: {target}",
                }
            )

    return errors, warnings, image_count


def normalize_heading_text(value: str) -> str:
    cleaned = re.sub(r"<[^>]+>", "", value)
    cleaned = re.sub(r"[：:]\s*$", "", cleaned.strip())
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def heading_level(line: str) -> int:
    match = re.match(r"^\s{0,3}(#{1,6})\s+", line)
    return len(match.group(1)) if match else 0


def extract_blueprint_headings(blueprint_path: Path) -> list[str]:
    text = blueprint_path.read_text(encoding="utf-8", errors="ignore")
    code_blocks = re.findall(r"```markdown\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    candidates: list[str] = []
    for block in code_blocks:
        block_headings = [
            normalize_heading_text(line.lstrip("#").strip())
            for line in block.splitlines()
            if line.startswith("#") and heading_level(line) <= 2
        ]
        if len(block_headings) > len(candidates):
            candidates = block_headings
    if candidates:
        return candidates
    return [
        normalize_heading_text(match.group("title"))
        for match in HEADING_RE.finditer(text)
        if text[match.start() : match.start() + 3].startswith("## ")
    ]


def note_top_headings(note_text: str) -> list[dict[str, Any]]:
    headings = []
    for match in HEADING_RE.finditer(note_text):
        raw_line = match.group(0)
        level = heading_level(raw_line)
        if level <= 2:
            headings.append(
                {
                    "title": normalize_heading_text(match.group("title")),
                    "line": note_text.count("\n", 0, match.start()) + 1,
                    "level": level,
                }
            )
    return headings


def heading_matches(actual: str, expected: str) -> bool:
    if not expected:
        return True
    if "<" in expected and ">" in expected:
        prefix = expected.split("<", 1)[0].strip()
        return not prefix or actual.startswith(prefix)
    return actual == expected or actual.startswith(expected + ":") or actual.startswith(expected + "：")


def is_optional_blueprint_heading(expected: str) -> bool:
    lowered = expected.lower()
    return any(
        token in lowered
        for token in (
            "appendix",
            "supplement",
            "post-reference",
            "references",
            "参考",
            "补充",
            "附录",
            "鍙傝",
            "琛ュ厖",
            "闄勫綍",
        )
    )


def check_blueprint_structure(note_text: str, blueprint_path: Path) -> list[dict[str, str | int]]:
    errors: list[dict[str, str | int]] = []
    if not blueprint_path.is_file():
        return [
            {
                "kind": "blueprint_not_found",
                "line": 0,
                "message": f"Blueprint file not found: {blueprint_path}",
            }
        ]

    expected = extract_blueprint_headings(blueprint_path)
    if not expected:
        return [
            {
                "kind": "blueprint_structure_unreadable",
                "line": 0,
                "message": f"No Markdown structure block or top headings could be read from: {blueprint_path}",
            }
        ]
    actual_headings = note_top_headings(note_text)
    actual_titles = [heading["title"] for heading in actual_headings]
    actual_index = 0

    for expected_title in expected:
        if not expected_title:
            continue
        found_index = None
        for index in range(actual_index, len(actual_titles)):
            if heading_matches(actual_titles[index], expected_title):
                found_index = index
                break
        if found_index is None:
            if is_optional_blueprint_heading(expected_title):
                continue
            errors.append(
                {
                    "kind": "missing_blueprint_heading",
                    "line": 0,
                    "message": f"Expected blueprint heading not found in order: {expected_title}",
                }
            )
        else:
            actual_index = found_index + 1

    if actual_headings and actual_headings[0]["level"] != 1:
        errors.append(
            {
                "kind": "missing_top_level_title",
                "line": int(actual_headings[0]["line"]),
                "message": "The first top-level heading should be an H1 note title.",
            }
        )
    return errors


def check_evidence_coverage(
    note_path: Path,
    note_text: str,
    manifest_path: Path,
    copy_map_path: Path | None = None,
    copy_map_authoritative: bool = False,
    strict_identity: bool = False,
    qa_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, str | int]]:
    """Check that high-confidence main-region matched assets appear in the note."""
    warnings: list[dict[str, str | int]] = []
    manifest = read_json(manifest_path)
    copy_map = read_json(copy_map_path) if copy_map_path and copy_map_path.is_file() else None
    items = iter_manifest_items(manifest)
    images = image_records(note_path, note_text)
    ordered_windows: list[dict[str, Any]] = []

    for item in items:
        label = item.get("label", "")
        if not label:
            continue
        required = bool(item.get("required_in_final"))
        high_confidence = item.get("match_confidence") == "high"
        expected_assets = []
        if high_confidence:
            expected_assets = expected_assets_for_item(
                item,
                copy_map,
                copy_map_authoritative,
                allow_basename_fallback=not strict_identity,
            )
        should_check_presence = required or high_confidence
        if not should_check_presence:
            continue

        window = evidence_window(note_text, str(label))
        if window is None:
            region = item.get("region", "main")
            if qa_rows is not None:
                qa_rows.append(
                    {
                        "item_key": item.get("item_key", ""),
                        "label": label,
                        "region": region,
                        "section": item.get("section", ""),
                        "manifest_block_index": item.get("block_index", ""),
                        "expected_assets": expected_assets,
                        "local_images": [],
                        "status": "missing_required_evidence"
                        if required
                        else "missing_evidence_reference",
                    }
                )
            warnings.append(
                {
                    "kind": "missing_required_evidence"
                    if required
                    else "missing_evidence_reference",
                    "line": 0,
                    "message": (
                        f"Required evidence item '{label}' ({region}) is not referenced in the note body."
                        if required
                        else f"High-confidence evidence item '{label}' ({region}) with matched asset is not referenced in the note body. Section: {item.get('section', 'unknown')}"
                    ),
                }
            )
            continue

        if item.get("region") == "main":
            ordered_windows.append(
                {
                    "label": label,
                    "order": int(item.get("order", 0) or 0),
                    "start": int(window["start"]),
                    "line": int(window["line"]),
                }
            )

        if copy_map_authoritative and copy_map is not None and not expected_assets:
            region = item.get("region", "main")
            if qa_rows is not None:
                qa_rows.append(
                    {
                        "item_key": item.get("item_key", ""),
                        "label": item.get("label", ""),
                        "region": region,
                        "section": item.get("section", ""),
                        "manifest_block_index": item.get("block_index", ""),
                        "expected_assets": [],
                        "local_images": [],
                        "status": "missing_copy_map_entry",
                    }
                )
            warnings.append(
                {
                    "kind": "missing_copy_map_entry",
                    "line": 0,
                    "message": (
                        f"High-confidence evidence item '{item.get('label', '')}' ({region}) "
                        "has matched assets in the manifest but no copy-map entry."
                    ),
                }
            )
            continue
        if not expected_assets:
            continue
        local_images = [
            record for record in images if int(window["start"]) <= int(record["start"]) < int(window["end"])
        ]
        found_asset = any(
            asset_matches_record(expected, record)
            for expected in expected_assets
            for record in local_images
        )
        found_elsewhere = any(
            asset_matches_record(expected, record)
            for expected in expected_assets
            for record in images
        )
        expected_names = ", ".join(
            asset.get("markdown") or asset.get("basename") or asset.get("source", "")
            for asset in expected_assets
        )
        status = "matched" if found_asset else "misplaced" if found_elsewhere else "missing_asset"
        if qa_rows is not None:
            qa_rows.append(
                {
                    "item_key": item.get("item_key", ""),
                    "label": label,
                    "region": item.get("region", "main"),
                    "section": item.get("section", ""),
                    "manifest_block_index": item.get("block_index", ""),
                    "window_line": int(window["line"]),
                    "window_title": window.get("title", ""),
                    "window_match_kind": window.get("match_kind", ""),
                    "window_score": window.get("score", ""),
                    "expected_assets": expected_assets,
                    "local_images": local_images,
                    "status": status,
                }
            )
        if found_elsewhere and not found_asset:
            region = item.get("region", "main")
            warnings.append(
                {
                    "kind": "misplaced_evidence_asset_link",
                    "line": int(window["line"]),
                    "message": (
                        f"High-confidence evidence item '{label}' ({region}) has a matched asset "
                        "linked outside its local evidence section/window. "
                        f"Expected locally: {expected_names}"
                    ),
                }
            )
        elif not found_asset:
            region = item.get("region", "main")
            warnings.append(
                {
                    "kind": "missing_evidence_asset_link",
                    "line": int(window["line"]),
                    "message": (
                        f"High-confidence evidence item '{label}' ({region}) appears in the note, "
                        "but none of its matched assets are linked in its local evidence window. "
                        f"Expected one of: {expected_names}"
                    ),
                }
            )
    previous: dict[str, Any] | None = None
    for current in sorted(ordered_windows, key=lambda row: row["order"]):
        if previous and current["start"] < previous["start"]:
            warnings.append(
                {
                    "kind": "evidence_order_error",
                    "line": int(current["line"]),
                    "message": (
                        f"Main-region evidence item '{current['label']}' appears before "
                        f"earlier manifest item '{previous['label']}'."
                    ),
                }
            )
        if previous is None or current["start"] > previous["start"]:
            previous = current
    return warnings


def write_qa_report(path: Path, note_path: Path, manifest_path: Path | None, rows: list[dict[str, Any]]) -> None:
    payload = {
        "schema_version": 1,
        "note": str(note_path),
        "manifest": str(manifest_path) if manifest_path else "",
        "total_items": len(rows),
        "matched_count": sum(1 for row in rows if row.get("status") == "matched"),
        "problem_count": sum(1 for row in rows if row.get("status") != "matched"),
        "items": rows,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def check_section_order(lines: list[str]) -> list[dict[str, str | int]]:
    warnings: list[dict[str, str | int]] = []
    discussion_section = None
    supplementary_section = None
    for index, line in enumerate(lines, start=1):
        heading = HEADING_RE.match(line)
        if not heading:
            continue
        title = heading.group("title")
        if ("七" in title or "九" in title) and "优点" in title and "局限" in title:
            discussion_section = index
        if ("八" in title or "十" in title) and "参考文献后" in title:
            supplementary_section = index
    if (
        supplementary_section is not None
        and discussion_section is not None
        and supplementary_section < discussion_section
    ):
        warnings.append(
            {
                "kind": "supplementary_section_before_discussion",
                "line": supplementary_section,
                "message": "The supplementary/post-reference section should appear after strengths, limitations, and discussion.",
            }
        )
    return warnings


def markdown_report(result: dict[str, object]) -> str:
    lines = [
        "# Note Validation",
        "",
        f"Note: {result['note']}",
        f"Assets dir: {result['assets_dir']}",
        f"Images checked: {result['image_count']}",
        f"Status: {result['status']}",
        "",
        "## Errors",
    ]
    errors = result["errors"]
    if errors:
        for error in errors:  # type: ignore[union-attr]
            lines.append(f"- line {error['line']}: [{error['kind']}] {error['message']}")
    else:
        lines.append("- <none>")
    lines.append("")
    lines.append("## Warnings")
    warnings = result["warnings"]
    if warnings:
        for warning in warnings:  # type: ignore[union-attr]
            lines.append(f"- line {warning['line']}: [{warning['kind']}] {warning['message']}")
    else:
        lines.append("- <none>")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    note_path = Path(args.note).expanduser().resolve()
    assets_dir = (
        Path(args.assets_dir).expanduser().resolve()
        if args.assets_dir
        else (note_path.parent / "assets").resolve()
    )

    text = note_path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    errors = []
    warnings = []
    errors.extend(check_banned_patterns(text))
    errors.extend(check_asset_dump(lines))
    link_errors, link_warnings, image_count = check_image_links(
        note_path, assets_dir, text, args.allow_wiki
    )
    errors.extend(link_errors)
    if args.strict_assets:
        errors.extend(
            warning
            for warning in link_warnings
            if warning["kind"] in {"remote_image", "non_assets_relative_image"}
        )
        warnings.extend(
            warning
            for warning in link_warnings
            if warning["kind"] not in {"remote_image", "non_assets_relative_image"}
        )
    else:
        warnings.extend(link_warnings)
    warnings.extend(check_section_order(lines))
    if args.blueprint:
        errors.extend(check_blueprint_structure(text, Path(args.blueprint).expanduser().resolve()))
    if args.evidence_manifest:
        manifest_path = Path(args.evidence_manifest).expanduser().resolve()
        if manifest_path.is_file():
            copy_map_path = Path(args.copy_map).expanduser().resolve() if args.copy_map else None
            if args.copy_map_authoritative and copy_map_path is None:
                errors.append(
                    {
                        "kind": "copy_map_required",
                        "line": 0,
                        "message": "--copy-map-authoritative requires --copy-map.",
                    }
                )
            elif args.copy_map_authoritative and not copy_map_path.is_file():
                errors.append(
                    {
                        "kind": "copy_map_not_found",
                        "line": 0,
                        "message": f"Copy map not found: {copy_map_path}",
                    }
                )
            qa_rows: list[dict[str, Any]] = []
            evidence_warnings = check_evidence_coverage(
                note_path,
                text,
                manifest_path,
                copy_map_path,
                args.copy_map_authoritative,
                args.strict_evidence,
                qa_rows,
            )
            if args.qa_report:
                write_qa_report(Path(args.qa_report).expanduser().resolve(), note_path, manifest_path, qa_rows)
            if args.strict_evidence:
                errors.extend(evidence_warnings)
            else:
                warnings.extend(evidence_warnings)
        else:
            errors.append(
                {
                    "kind": "manifest_not_found",
                    "line": 0,
                    "message": f"Evidence manifest not found: {manifest_path}",
                }
            )
    elif args.qa_report:
        write_qa_report(Path(args.qa_report).expanduser().resolve(), note_path, None, [])

    result = {
        "note": str(note_path),
        "assets_dir": str(assets_dir),
        "image_count": image_count,
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "warnings": warnings,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(markdown_report(result))

    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
