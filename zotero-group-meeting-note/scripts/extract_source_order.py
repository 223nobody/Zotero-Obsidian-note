#!/usr/bin/env python3
"""Extract a first-pass source-order inventory for paper evidence items."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


LABEL_RE = re.compile(
    r"\b(?P<kind>Figure|Fig\.|Table|Equation|Eq\.)\s*"
    r"(?P<label>\(?[A-Za-z]?\d+(?:[.\-][A-Za-z0-9]+)?\)?)",
    re.IGNORECASE,
)
SPECIAL_RE = re.compile(
    r"\b(?P<kind>Objective|Loss|Score|Constraint)\s*"
    r"(?P<label>\(?[A-Za-z]?\d+(?:[.\-][A-Za-z0-9]+)?\)?)?"
)
IMAGE_RE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<path>[^)]+)\)")
WIKI_IMAGE_RE = re.compile(
    r"!\[\[(?P<path>[^\]|#]+)(?:#[^\]|]+)?(?:\|(?P<alt>[^\]]+))?\]\]"
)
CAPTION_HINT_RE = re.compile(r"\b(Figure|Fig\.|Table|Equation|Eq\.)\s*\d+", re.IGNORECASE)
HEADING_RE = re.compile(r"^(?P<marks>#{1,6})\s+(?P<title>.+?)\s*$")
APPENDIX_RE = re.compile(
    r"\b(appendix|supplementary|supplemental|additional results|附录|补充材料)\b",
    re.IGNORECASE,
)
REFERENCES_RE = re.compile(
    r"^\s*(references|bibliography|参考文献|参考资料)\s*$",
    re.IGNORECASE,
)
REFERENCE_PHRASE_RE = re.compile(
    r"\b(as shown in|shown in|see|refer to|in|from|according to)\s+"
    r"(Figure|Fig\.|Table|Equation|Eq\.)\s*\d+",
    re.IGNORECASE,
)
CAPTION_PREFIX_RE = re.compile(
    r"^\s*(?:\*\*)?\s*(Figure|Fig\.|Table|Equation|Eq\.)\s*\d+[\s:.\-]",
    re.IGNORECASE,
)
TABLE_ROW_RE = re.compile(
    r"^\s*\|\s*(?:\*\*)?\s*(Table|Figure|Fig\.|Equation|Eq\.)\s*\d+",
    re.IGNORECASE,
)
CORE_HINT_RE = re.compile(
    r"\b(method|overview|architecture|framework|pipeline|algorithm|objective|loss|main result|"
    r"ablation|comparison|performance|robustness|generalization|efficiency|theorem)\b",
    re.IGNORECASE,
)
NON_CORE_HINT_RE = re.compile(
    r"\b(supplementary|appendix|additional|example|examples|case study|visualization|"
    r"statistics|distribution|implementation detail)\b",
    re.IGNORECASE,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a mixed Figure/Table/Equation source-order inventory from Markdown or text."
    )
    parser.add_argument("paths", nargs="+", help="Markdown/text files to scan.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown.")
    parser.add_argument(
        "--include-mentions",
        action="store_true",
        help="Include non-caption prose mentions. By default repeated mentions are collapsed.",
    )
    return parser.parse_args()


def iter_input_files(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        path = Path(raw).expanduser()
        if path.is_dir():
            files.extend(
                child
                for child in sorted(path.rglob("*"))
                if child.is_file() and child.suffix.lower() in {".md", ".markdown", ".txt"}
            )
        elif path.is_file():
            files.append(path)
    return files


def normalize_type(kind: str) -> str:
    lowered = kind.lower().rstrip(".")
    if lowered in {"figure", "fig"}:
        return "Figure"
    if lowered == "table":
        return "Table"
    if lowered in {"equation", "eq"}:
        return "Equation"
    return kind[:1].upper() + kind[1:].lower()


def normalize_label(kind: str, raw_label: str | None) -> str:
    label = (raw_label or "").strip()
    label = label.strip("()")
    return f"{kind} {label}".strip()


def nearby_text(lines: list[str], index: int) -> str:
    candidates: list[str] = []
    for offset in (0, 1, -1, 2, -2):
        pos = index + offset
        if 0 <= pos < len(lines):
            text = lines[pos].strip().lstrip("\ufeff")
            if text and not text.startswith("```"):
                candidates.append(text)
    return " ".join(candidates)[:240]


def normalize_heading(line: str) -> str | None:
    match = HEADING_RE.match(line.strip().lstrip("\ufeff"))
    if not match:
        return None
    return match.group("title").strip()


def clean_heading_title(title: str) -> str:
    cleaned = title.strip()
    cleaned = re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", cleaned)
    cleaned = re.sub(
        r"^(section|chapter)\s+\d+(?:\.\d+)*\.?\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip()


def section_region(
    title: str | None, current_region: str, seen_references: bool
) -> tuple[str, bool]:
    if not title:
        return current_region, seen_references

    cleaned = clean_heading_title(title)
    if REFERENCES_RE.match(cleaned):
        return "references", True
    if seen_references:
        return "post_reference", True
    if APPENDIX_RE.search(cleaned):
        return "appendix", seen_references
    return "main", seen_references


def source_role(line: str, from_image: bool = False) -> str:
    stripped = line.strip().lstrip("\ufeff")
    if from_image:
        return "object"
    if stripped.startswith("!") or CAPTION_PREFIX_RE.search(stripped) or TABLE_ROW_RE.search(stripped):
        return "caption"
    if REFERENCE_PHRASE_RE.search(stripped):
        return "prose_reference"
    if re.match(r"^\s*(?:\*\*)?\s*(Figure|Fig\.|Table|Equation|Eq\.)\s*\d+", stripped, re.IGNORECASE):
        return "caption_candidate"
    return "prose_reference"


def include_role(role: str, include_mentions: bool) -> bool:
    if role in {"object", "caption", "caption_candidate"}:
        return True
    return include_mentions


def attach_asset_to_existing(
    items: list[dict[str, str | int]],
    label: str,
    asset_path: str,
    current_section: str,
    current_region: str,
    line_no: int,
    max_line_gap: int = 4,
) -> bool:
    if not asset_path:
        return False
    for item in reversed(items):
        if item.get("label") != label or item.get("asset_path"):
            continue
        item_line = int(str(item.get("line_no", line_no)))
        same_region = item.get("region") == current_region
        same_section = item.get("section") == current_section
        nearby = 0 <= line_no - item_line <= max_line_gap
        if same_region and (same_section or nearby):
            item["asset_path"] = asset_path
            return True
    return False


def is_probable_special_line(line: str) -> bool:
    stripped = line.strip().lstrip("\ufeff")
    if not stripped:
        return False
    if stripped.startswith(("#", "**", "$$", "- **")):
        return True
    return bool(re.match(r"^(Objective|Loss|Score|Constraint)\b", stripped))


def core_guess(item_type: str, primary_text: str, context_text: str) -> tuple[str, str, str]:
    if NON_CORE_HINT_RE.search(primary_text) and not CORE_HINT_RE.search(primary_text):
        return "non_core_candidate", "caption suggests auxiliary or supplementary evidence", "compressed"
    if item_type == "Equation":
        return "core_candidate", "formula-like item usually needs method-level review", "full"
    if CORE_HINT_RE.search(primary_text):
        return "core_candidate", "caption or nearby text contains core-evidence keywords", "full"
    if CORE_HINT_RE.search(context_text) and not NON_CORE_HINT_RE.search(context_text):
        return "core_candidate", "nearby text contains core-evidence keywords; verify manually", "full"
    return "non_core_candidate", "no obvious core-evidence keyword in caption or nearby text", "compressed"


def extract_items(path: Path, include_mentions: bool) -> list[dict[str, str | int]]:
    text = path.read_text(encoding="utf-8", errors="ignore").lstrip("\ufeff")
    lines = text.splitlines()
    items: list[dict[str, str | int]] = []
    seen_labels: set[str] = set()
    current_section = "<front matter>"
    current_region = "main"
    seen_references = False
    nearby_unlabeled_images: list[tuple[int, str]] = []

    for line_no, line in enumerate(lines, start=1):
        line_index = line_no - 1
        heading = normalize_heading(line)
        if heading:
            current_section = heading
            current_region, seen_references = section_region(
                heading, current_region, seen_references
            )
            nearby_unlabeled_images = []
            if current_region != "references":
                heading_match = LABEL_RE.search(heading)
                if heading_match:
                    item_type = normalize_type(heading_match.group("kind"))
                    label = normalize_label(item_type, heading_match.group("label"))
                    if label not in seen_labels or include_mentions:
                        seen_labels.add(label)
                        items.append(
                            build_item(
                                path,
                                line_no,
                                item_type,
                                label,
                                heading,
                                nearby_text(lines, line_index),
                                current_section,
                                current_region,
                                "caption_candidate",
                                "",
                            )
                        )
            continue

        if current_region == "references":
            continue

        image_labels_on_line: set[str] = set()
        for image_match in IMAGE_RE.finditer(line):
            alt = image_match.group("alt").strip()
            image_path = image_match.group("path").strip()
            match = LABEL_RE.search(alt) or LABEL_RE.search(image_match.group("path"))
            if not match:
                if items:
                    last_line = int(str(items[-1].get("line_no", line_no)))
                    if (
                        line_no - last_line <= 3
                        and not items[-1].get("asset_path")
                        and items[-1].get("section") == current_section
                    ):
                        items[-1]["asset_path"] = image_path
                nearby_unlabeled_images.append((line_no, image_path))
                nearby_unlabeled_images = [
                    item for item in nearby_unlabeled_images if line_no - item[0] <= 3
                ]
                continue
            item_type = normalize_type(match.group("kind"))
            label = normalize_label(item_type, match.group("label"))
            image_labels_on_line.add(label)
            role = source_role(line, from_image=True)
            if label in seen_labels and not include_mentions:
                attach_asset_to_existing(
                    items, label, image_path, current_section, current_region, line_no
                )
                continue
            seen_labels.add(label)
            items.append(
                build_item(
                    path,
                    line_no,
                    item_type,
                    label,
                    line,
                    nearby_text(lines, line_index),
                    current_section,
                    current_region,
                    role,
                    image_path,
                )
            )

        for image_match in WIKI_IMAGE_RE.finditer(line):
            alt = (image_match.group("alt") or "").strip()
            image_path = image_match.group("path").strip()
            match = LABEL_RE.search(alt) or LABEL_RE.search(image_path)
            if not match:
                if items:
                    last_line = int(str(items[-1].get("line_no", line_no)))
                    if (
                        line_no - last_line <= 3
                        and not items[-1].get("asset_path")
                        and items[-1].get("section") == current_section
                    ):
                        items[-1]["asset_path"] = image_path
                nearby_unlabeled_images.append((line_no, image_path))
                nearby_unlabeled_images = [
                    item for item in nearby_unlabeled_images if line_no - item[0] <= 3
                ]
                continue
            item_type = normalize_type(match.group("kind"))
            label = normalize_label(item_type, match.group("label"))
            image_labels_on_line.add(label)
            role = source_role(line, from_image=True)
            if label in seen_labels and not include_mentions:
                attach_asset_to_existing(
                    items, label, image_path, current_section, current_region, line_no
                )
                continue
            seen_labels.add(label)
            items.append(
                build_item(
                    path,
                    line_no,
                    item_type,
                    label,
                    line,
                    nearby_text(lines, line_index),
                    current_section,
                    current_region,
                    role,
                    image_path,
                )
            )

        role = source_role(line)
        for match in LABEL_RE.finditer(line):
            item_type = normalize_type(match.group("kind"))
            label = normalize_label(item_type, match.group("label"))
            if label in image_labels_on_line:
                continue
            if label in seen_labels and not include_mentions:
                if role in {"caption", "caption_candidate"} and nearby_unlabeled_images:
                    attached = attach_asset_to_existing(
                        items,
                        label,
                        "; ".join(image for _, image in nearby_unlabeled_images),
                        current_section,
                        current_region,
                        line_no,
                    )
                    if attached:
                        nearby_unlabeled_images = []
                continue
            if not include_role(role, include_mentions):
                continue
            seen_labels.add(label)
            asset_path = ""
            if role in {"caption", "caption_candidate"} and nearby_unlabeled_images:
                asset_path = "; ".join(image for _, image in nearby_unlabeled_images)
                nearby_unlabeled_images = []
            items.append(
                build_item(
                    path,
                    line_no,
                    item_type,
                    label,
                    line,
                    nearby_text(lines, line_index),
                    current_section,
                    current_region,
                    role,
                    asset_path,
                )
            )

        if is_probable_special_line(line):
            for match in SPECIAL_RE.finditer(line):
                item_type = normalize_type(match.group("kind"))
                label = normalize_label(item_type, match.group("label"))
                if label in seen_labels and not include_mentions:
                    continue
                seen_labels.add(label)
                items.append(
                    build_item(
                        path,
                        line_no,
                        item_type,
                        label,
                        line,
                        nearby_text(lines, line_index),
                        current_section,
                        current_region,
                        "object",
                        "",
                    )
                )

    return items


def build_item(
    path: Path,
    line_no: int,
    item_type: str,
    label: str,
    primary_text: str,
    context_text: str,
    section: str,
    region: str,
    role: str,
    asset_path: str = "",
) -> dict[str, str | int]:
    core_level, rationale, style = core_guess(item_type, primary_text, context_text)
    if region in {"appendix", "post_reference"} and core_level == "core_candidate":
        core_level = "non_core_candidate"
        rationale = f"{region} item; keep separate from main-paper evidence unless it directly supports a main claim ({rationale})"
        style = "compressed"
    if role == "prose_reference":
        rationale = "prose reference, not object/caption; verify object location before ordering"
        style = "compressed"
    return {
        "type": item_type,
        "label": label,
        "first_location": f"{path.name}:{line_no}",
        "line_no": line_no,
        "section": section,
        "region": region,
        "asset_path": asset_path,
        "source_role": role,
        "caption_or_nearby_text": context_text,
        "status": "available",
        "core_level": core_level,
        "rationale": rationale,
        "final_entry_style": style,
    }


def markdown_table(items: list[dict[str, str | int]]) -> str:
    lines = [
        "# Source-Order Inventory",
        "",
        "| order | type | label | first location | section | region | asset path | source role | caption / nearby text | status | core level | rationale | final entry style |",
        "| ----- | ---- | ----- | -------------- | ------- | ------ | ---------- | ----------- | --------------------- | ------ | ---------- | --------- | ----------------- |",
    ]
    for index, item in enumerate(items, start=1):
        nearby = str(item["caption_or_nearby_text"]).replace("|", "\\|")
        section = str(item["section"]).replace("|", "\\|")
        asset_path = str(item.get("asset_path", "")).replace("|", "\\|") or "<none>"
        lines.append(
            f"| {index} | {item['type']} | {item['label']} | {item['first_location']} | "
            f"{section} | {item['region']} | {asset_path} | {item['source_role']} | {nearby} | "
            f"{item['status']} | {item['core_level']} | {item['rationale']} | "
            f"{item['final_entry_style']} |"
        )
    if not items:
        lines.append(
            "| <none> | <none> | <none> | <none> | <none> | main | <none> | object | <none> | "
            "missing | non_core_candidate | <none> | compressed |"
        )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    files = iter_input_files(args.paths)
    items: list[dict[str, str | int]] = []
    for path in files:
        items.extend(extract_items(path, args.include_mentions))

    for index, item in enumerate(items, start=1):
        item["order"] = index

    if args.json:
        print(json.dumps({"files": [str(path) for path in files], "items": items}, ensure_ascii=False, indent=2))
    else:
        print(markdown_table(items))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
