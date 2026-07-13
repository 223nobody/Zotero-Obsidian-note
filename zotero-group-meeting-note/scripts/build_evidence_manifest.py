#!/usr/bin/env python3
"""Build a source-ordered evidence/asset manifest from MinerU content_list.json."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


LABEL_RE = re.compile(
    r"\b(?P<kind>Figure|Fig\.|Table|Equation|Eq\.|Algorithm|Alg\.|Proposition|Theorem|Lemma)\s*"
    r"(?P<label>\(?[A-Za-z]?\d+(?:[.\-][A-Za-z0-9]+)?\)?)",
    re.IGNORECASE,
)
SPECIAL_RE = re.compile(
    r"\b(?P<kind>Objective|Loss|Score|Constraint|Prompt|Case Study|Checklist)\s*"
    r"(?P<label>\(?[A-Za-z]?\d+(?:[.\-][A-Za-z0-9]+)?\)?)?",
    re.IGNORECASE,
)
EQUATION_TAG_RE = re.compile(
    r"\\tag\s*\{?\s*\(?\s*(?P<label>[A-Za-z]?\d+(?:[.\-][A-Za-z0-9]+)?)\s*\)?\s*\}?",
    re.IGNORECASE,
)
LATEX_HINT_RE = re.compile(
    r"(?:\$\$|\\frac|\\sum|\\prod|\\mathcal|\\mathrm|\\sigma|\\log|\\exp|_|\\tag)",
    re.IGNORECASE,
)
LOSS_HINT_RE = re.compile(
    r"(?:\\mathcal\s*\{\s*L\s*\}|\\mathcal\s*\{\s*\\?L\s*\}|loss|objective|cross-entropy|"
    r"bce|infonce|contrastive)",
    re.IGNORECASE,
)
REFERENCES_RE = re.compile(
    r"^\s*(references|bibliography|参考文献|参考资料)\s*$",
    re.IGNORECASE,
)
APPENDIX_RE = re.compile(
    r"\b(appendix|supplementary|supplemental|additional results|prompt|case study|"
    r"implementation details|ethics|checklist|附录|补充材料)\b",
    re.IGNORECASE,
)
CORE_HINT_RE = re.compile(
    r"\b(method|overview|architecture|framework|pipeline|algorithm|objective|loss|main result|"
    r"ablation|comparison|performance|robustness|generalization|efficiency|theorem|proposition|"
    r"training dynamic|hyperparameter|case study)\b",
    re.IGNORECASE,
)
NON_CORE_HINT_RE = re.compile(
    r"\b(supplementary|appendix|additional|example|examples|visualization|"
    r"statistics|distribution|implementation detail|checklist)\b",
    re.IGNORECASE,
)
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
ASSET_KEY_RE = re.compile(
    r"(^|_)(?:path|paths|img|image|asset|figure|formula|table)(?:$|_)",
    re.IGNORECASE,
)
NON_ASSET_KEY_RE = re.compile(
    r"(?:body|html|text|caption|content|latex|title|alt|code)",
    re.IGNORECASE,
)
TEXT_KEY_RE = re.compile(r"(?:text|caption|content|html|latex|title|alt|code_body)$", re.IGNORECASE)
TYPE_KEY_RE = re.compile(r"(?:type|category|block_type)", re.IGNORECASE)
PAGE_KEY_RE = re.compile(r"(?:page|page_idx|page_no|page_number)", re.IGNORECASE)
CONTENT_KEY_RE = re.compile(
    r"(?:text|caption|content|html|latex|body|table_body|code_body|markdown)$",
    re.IGNORECASE,
)
CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}
TYPE_TO_KIND = {
    "Figure": "figure",
    "Table": "table",
    "Equation": "equation",
    "Algorithm": "algorithm",
    "Objective": "equation",
    "Loss": "equation",
    "Score": "equation",
    "Constraint": "equation",
    "Proposition": "equation",
    "Theorem": "equation",
    "Lemma": "equation",
    "Prompt": "prompt",
    "Case Study": "prompt",
    "Checklist": "prompt",
}
EQUATION_LIKE_SPECIAL_TYPES = {"Objective", "Loss", "Score", "Constraint"}
UNLABELED_SPECIAL_TYPES = EQUATION_LIKE_SPECIAL_TYPES | {"Prompt", "Case Study", "Checklist"}
SUPPLEMENTARY_LABEL_PREFIX_RE = re.compile(
    r"^\s*(?:Appendix|Supplementary|Supplemental|Additional|补充|附录)\b",
    re.IGNORECASE,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a source-order evidence manifest from MinerU content_list.json."
    )
    parser.add_argument("content_list", nargs="?", help="MinerU content_list.json path.")
    parser.add_argument(
        "--source-pack",
        help=(
            "Optional per-paper source_pack.json. Missing content_list, assets_dir, "
            "full_md, title, and note paths are read from it."
        ),
    )
    parser.add_argument(
        "--assets-dir",
        help="MinerU assets directory used to resolve relative asset paths.",
    )
    parser.add_argument(
        "--full-md",
        help="Optional full.md path, recorded for provenance in the output.",
    )
    parser.add_argument("--output", help="Optional output path. Defaults to stdout.")
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Emit a Markdown table instead of JSON.",
    )
    parser.add_argument(
        "--min-confidence",
        default="medium",
        choices=["high", "medium", "low"],
        help="Minimum match confidence to include. Default: medium.",
    )
    parser.add_argument(
        "--split-regions",
        action="store_true",
        help="Output separate main_items and post_reference_items arrays for routing.",
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig", errors="ignore"))


def normalize_type(kind: str) -> str:
    lowered = kind.lower().rstrip(".")
    mapping = {
        "figure": "Figure",
        "fig": "Figure",
        "table": "Table",
        "equation": "Equation",
        "eq": "Equation",
        "algorithm": "Algorithm",
        "alg": "Algorithm",
        "proposition": "Proposition",
        "theorem": "Theorem",
        "lemma": "Lemma",
    }
    return mapping.get(lowered, " ".join(part.capitalize() for part in kind.split()))


def normalize_label(kind: str, raw_label: str | None) -> str:
    label = (raw_label or "").strip().strip("()")
    return f"{kind} {label}".strip()


def contextual_label(text: str, match: re.Match[str], item_type: str) -> str:
    label = normalize_label(item_type, match.group("label"))
    prefix_window = text[max(0, match.start() - 32) : match.start()]
    prefix_match = re.search(
        r"(Supplementary|Supplemental|Appendix|Additional|补充|附录)\s*$",
        prefix_window,
        re.IGNORECASE,
    )
    if not prefix_match:
        return label
    prefix = prefix_match.group(1)
    normalized = {
        "supplemental": "Supplementary",
        "supplementary": "Supplementary",
        "additional": "Additional",
        "appendix": "Appendix",
    }.get(prefix.lower(), prefix)
    return f"{normalized} {label}"


def clean_heading(title: str) -> str:
    cleaned = title.strip().lstrip("#").strip()
    cleaned = re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", cleaned)
    cleaned = re.sub(
        r"^(section|chapter)\s+\d+(?:\.\d+)*\.?\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip()


def stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return " ".join(stringify(item) for item in value)
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            if TEXT_KEY_RE.search(str(key)):
                parts.append(stringify(item))
        return " ".join(parts)
    return str(value)


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


def block_text(block: dict[str, Any]) -> str:
    preferred: list[str] = []
    fallback: list[str] = []
    for key, value in block.items():
        text = stringify(value).strip()
        if not text:
            continue
        if TEXT_KEY_RE.search(str(key)):
            preferred.append(text)
        elif (
            isinstance(value, str)
            and not ASSET_KEY_RE.search(str(key))
            and not TYPE_KEY_RE.search(str(key))
            and not PAGE_KEY_RE.search(str(key))
        ):
            fallback.append(text)
    combined = " ".join(preferred or fallback)
    return re.sub(r"\s+", " ", combined).strip()


def content_payload(block: dict[str, Any]) -> dict[str, str]:
    payload: dict[str, str] = {}
    for key, value in block.items():
        key_text = str(key)
        if not CONTENT_KEY_RE.search(key_text):
            continue
        if ASSET_KEY_RE.search(key_text) and not NON_ASSET_KEY_RE.search(key_text):
            continue
        text = stringify(value).strip()
        if text:
            payload[key_text] = text[:5000]
    return payload


def page_number(block: dict[str, Any]) -> str:
    for key, value in block.items():
        if PAGE_KEY_RE.search(str(key)) and isinstance(value, (str, int, float)):
            return str(value)
    return ""


def resolve_asset_path(raw: str, assets_dir: Path | None) -> Path | None:
    path_text = raw.split("#", 1)[0].split("?", 1)[0].replace("\\", "/")
    path = Path(path_text)
    if path.is_absolute():
        return path
    if assets_dir:
        candidates = [
            (assets_dir / path_text).resolve(),
            (assets_dir / path.name).resolve(),
            (assets_dir / "figures" / path.name).resolve(),
            (assets_dir / "tables" / path.name).resolve(),
            (assets_dir / "equations" / path.name).resolve(),
            (assets_dir / "images" / path.name).resolve(),
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate
    return None


def asset_candidates(block: dict[str, Any], assets_dir: Path | None) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()
    for key, value in walk_strings(block):
        if NON_ASSET_KEY_RE.search(key):
            continue
        raw = value.strip().strip("<>")
        if not raw:
            continue
        suffix = Path(raw.split("#", 1)[0].split("?", 1)[0]).suffix.lower()
        if not ASSET_KEY_RE.search(key) and suffix not in IMAGE_EXTENSIONS:
            continue
        if suffix and suffix not in IMAGE_EXTENSIONS:
            continue
        if not suffix and not ASSET_KEY_RE.search(key):
            continue
        if raw in seen:
            continue
        seen.add(raw)
        resolved = resolve_asset_path(raw, assets_dir)
        if not resolved and suffix not in IMAGE_EXTENSIONS:
            continue
        candidates.append(
            {
                "path": raw,
                "resolved_path": str(resolved) if resolved else "",
                "exists": "yes" if resolved and resolved.is_file() else "unknown",
                "source_key": key,
                "kind": infer_asset_kind(raw, key, block_type(block)),
            }
        )
    return candidates


def infer_asset_kind(path_text: str, source_key: str = "", btype: str = "") -> str:
    haystack = " ".join([path_text, source_key, btype]).lower()
    if any(token in haystack for token in ("table", "tabular", "grid")):
        return "table"
    if any(token in haystack for token in ("equation", "formula", "latex", "loss", "objective")):
        return "equation"
    if any(token in haystack for token in ("algorithm", "alg")):
        return "algorithm"
    if any(token in haystack for token in ("prompt", "case", "checklist")):
        return "prompt"
    if any(token in haystack for token in ("figure", "fig", "image", "img")):
        return "figure"
    return "unknown"


def canonical_asset_paths(assets: list[dict[str, str]]) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for asset in assets:
        value = asset.get("resolved_path") or asset.get("path") or ""
        if not value or value in seen:
            continue
        seen.add(value)
        paths.append(value)
    return paths


def file_sha256(path_text: str) -> str:
    path = Path(path_text)
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_dimensions(path: Path) -> tuple[int, int] | None:
    """Read common image dimensions without requiring Pillow."""
    try:
        with path.open("rb") as handle:
            header = handle.read(32)
            if header.startswith(b"\x89PNG\r\n\x1a\n") and len(header) >= 24:
                width = int.from_bytes(header[16:20], "big")
                height = int.from_bytes(header[20:24], "big")
                return width, height
            if header[:3] == b"GIF" and len(header) >= 10:
                width = int.from_bytes(header[6:8], "little")
                height = int.from_bytes(header[8:10], "little")
                return width, height
            if header.startswith(b"\xff\xd8"):
                handle.seek(2)
                while True:
                    marker_prefix = handle.read(1)
                    if not marker_prefix:
                        return None
                    if marker_prefix != b"\xff":
                        continue
                    marker = handle.read(1)
                    while marker == b"\xff":
                        marker = handle.read(1)
                    if not marker:
                        return None
                    marker_value = marker[0]
                    if marker_value in {0xD8, 0xD9}:
                        continue
                    length_bytes = handle.read(2)
                    if len(length_bytes) != 2:
                        return None
                    segment_length = int.from_bytes(length_bytes, "big")
                    if segment_length < 2:
                        return None
                    if marker_value in {
                        0xC0,
                        0xC1,
                        0xC2,
                        0xC3,
                        0xC5,
                        0xC6,
                        0xC7,
                        0xC9,
                        0xCA,
                        0xCB,
                        0xCD,
                        0xCE,
                        0xCF,
                    }:
                        data = handle.read(5)
                        if len(data) != 5:
                            return None
                        height = int.from_bytes(data[1:3], "big")
                        width = int.from_bytes(data[3:5], "big")
                        return width, height
                    handle.seek(segment_length - 2, 1)
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
    # MinerU formula crops are usually short, wide, and much smaller than tables.
    return height <= 140 and width >= 120 and ratio >= 2.0 and size <= 25000


def image_width(path: Path) -> int:
    dims = image_dimensions(path)
    return dims[0] if dims else 0


def page_distance_ok(left: dict[str, Any], right: dict[str, Any], max_delta: int = 1) -> bool:
    if same_page_or_unknown(left, right):
        return True
    try:
        left_page = int(float(str(left.get("page", "") or "")))
        right_page = int(float(str(right.get("page", "") or "")))
    except ValueError:
        return False
    return abs(left_page - right_page) <= max_delta


def update_region(text: str, current_region: str, seen_references: bool) -> tuple[str, bool]:
    title = clean_heading(text)
    if REFERENCES_RE.match(title):
        return "references", True
    if seen_references:
        return "post_reference", True
    if APPENDIX_RE.search(title):
        return "appendix", seen_references
    return current_region, seen_references


def source_role(block: dict[str, Any], text: str, assets: list[dict[str, str]]) -> str:
    btype = block_type(block).lower()
    if assets:
        return "object"
    if "equation" in btype or "formula" in btype:
        return "equation"
    if "caption" in btype or LABEL_RE.match(text):
        return "caption"
    if "title" in btype or "heading" in btype:
        return "caption_candidate"
    return "prose_reference"


def find_labels(text: str) -> list[tuple[str, str]]:
    labels: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for match in LABEL_RE.finditer(text):
        item_type = normalize_type(match.group("kind"))
        label = contextual_label(text, match, item_type)
        key = (item_type, label)
        if key not in seen:
            labels.append(key)
            seen.add(key)
    for match in SPECIAL_RE.finditer(text):
        item_type = normalize_type(match.group("kind"))
        label = normalize_label(item_type, match.group("label"))
        key = (item_type, label)
        if key not in seen:
            labels.append(key)
            seen.add(key)
    return labels


def is_equation_block(btype: str, text: str) -> bool:
    lowered = btype.lower()
    stripped = text.strip()
    return (
        "equation" in lowered
        or "formula" in lowered
        or (stripped.startswith("$$") and LATEX_HINT_RE.search(stripped) is not None)
    )


def filter_contextual_labels(
    labels: list[tuple[str, str]],
    btype: str,
    text: str,
) -> list[tuple[str, str]]:
    """Keep explicit labels; treat unlabeled equation-like words as hints only."""
    if not labels:
        return labels
    filtered: list[tuple[str, str]] = []
    for item_type, label in labels:
        if item_type not in UNLABELED_SPECIAL_TYPES:
            filtered.append((item_type, label))
            continue
        # SPECIAL_RE can match ordinary prose such as "InfoNCE loss" or
        # "prompt template". Without a numeric tag, keep it as context. Real
        # equation/formula blocks will still receive stable inferred labels.
        if label.strip().lower() == item_type.lower():
            continue
        filtered.append((item_type, label))
    return filtered


def appendix_section_prefix(section: str) -> str:
    cleaned = section.strip()
    match = re.match(
        r"\s*(?:appendix|supplementary|supplement|附录)\s+([A-Z])(?:\b|[.\s:-])",
        cleaned,
        re.IGNORECASE,
    )
    if not match:
        match = re.match(r"\s*([A-Z])(?:\b|[.\s:-])", cleaned)
    return match.group(1) if match else ""


def infer_equation_labels(
    btype: str,
    text: str,
    section: str,
    region: str,
    page: str,
    counters: dict[tuple[str, str, str], int],
) -> list[tuple[str, str]]:
    if not is_equation_block(btype, text):
        return []
    item_type = "Loss" if LOSS_HINT_RE.search(text) else "Equation"
    tag_match = EQUATION_TAG_RE.search(text)
    if tag_match:
        return [(item_type, normalize_label(item_type, tag_match.group("label")))]

    counter_key = (region, section, item_type)
    counters[counter_key] = counters.get(counter_key, 0) + 1
    prefix = appendix_section_prefix(section) if region in {"appendix", "post_reference"} else ""
    if prefix:
        label_id = f"{prefix}{counters[counter_key]}"
    else:
        label_id = f"p{page or 'x'}-{counters[counter_key]}"
    return [(item_type, normalize_label(item_type, label_id))]


def infer_label_from_block(block: dict[str, Any], assets: list[dict[str, str]]) -> tuple[str, str] | None:
    btype = block_type(block).lower()
    type_hint = ""
    if "image" in btype or "figure" in btype:
        type_hint = "Figure"
    elif "table" in btype:
        type_hint = "Table"
    elif "equation" in btype or "formula" in btype:
        type_hint = "Equation"
    elif "algorithm" in btype:
        type_hint = "Algorithm"
    if not type_hint:
        for asset in assets:
            path = asset["path"].lower()
            if "table" in path:
                type_hint = "Table"
            elif "equation" in path or "formula" in path or "loss" in path:
                type_hint = "Equation"
            elif "algorithm" in path or "alg" in path:
                type_hint = "Algorithm"
            elif "figure" in path or "fig" in path:
                type_hint = "Figure"
            if type_hint:
                break
    if not type_hint:
        return None
    for asset in assets:
        asset_stem = Path(asset["path"].split("#", 1)[0].split("?", 1)[0]).stem
        match = re.search(
            r"(?:fig(?:ure)?|table|eq(?:uation)?|formula|algorithm|alg)[-_ ]*"
            r"([A-Za-z]?\d+(?:[.\-][A-Za-z0-9]+)?)",
            asset_stem,
            re.IGNORECASE,
        )
        if match:
            return type_hint, f"{type_hint} {match.group(1)}"
    return type_hint, f"{type_hint} candidate"


def core_guess(item_type: str, text: str, region: str) -> tuple[str, str]:
    if region in {"appendix", "post_reference"}:
        return (
            "non_core_candidate",
            "supplementary/post-reference item; keep outside main evidence timeline unless it changes a main claim",
        )
    if item_type in {"Equation", "Algorithm", "Proposition", "Theorem", "Lemma"}:
        return "core_candidate", "method/theory item usually needs method-level review"
    if CORE_HINT_RE.search(text):
        return "core_candidate", "caption or nearby text contains core-evidence keywords"
    if NON_CORE_HINT_RE.search(text):
        return "non_core_candidate", "caption suggests auxiliary or supplementary evidence"
    return "non_core_candidate", "no obvious core-evidence keyword; verify manually"


def confidence(role: str, label: str, assets: list[dict[str, str]], text: str) -> tuple[str, str]:
    if role in {"caption", "object"} and "candidate" not in label.lower() and assets:
        return "high", "label and asset appear in the same structured block"
    if role in {"caption", "caption_candidate"} and "candidate" not in label.lower():
        return "medium", "label is visible but no direct asset was found in the same block"
    if assets and "candidate" in label.lower():
        return "low", "asset type was inferred without a reliable paper label"
    if LABEL_RE.search(text):
        return "medium", "label was found in nearby text"
    return "low", "requires manual confirmation"


def merged_confidence(
    role: str,
    label: str,
    asset_paths: list[str],
    own_asset_paths: list[str],
    text: str,
) -> tuple[str, str]:
    if "candidate" in label.lower() and asset_paths:
        return "low", "asset type was inferred without a reliable paper label"
    if own_asset_paths and role in {"caption", "object"}:
        return "high", "label and asset appear in the same structured block"
    if role in {"equation", "formula"} and asset_paths:
        return "medium", "equation block was matched with a formula image candidate"
    if role in {"equation", "formula"} and "candidate" not in label.lower():
        return "medium", "equation block is explicit but no direct image asset was found"
    if asset_paths and role in {"caption", "caption_candidate", "prose_reference"}:
        return "high", "label and asset were merged from adjacent structured blocks"
    if role in {"caption", "caption_candidate"} and "candidate" not in label.lower():
        return "medium", "label is visible but no direct or adjacent asset was found"
    if LABEL_RE.search(text):
        return "medium", "label was found in nearby text"
    return "low", "requires manual confirmation"


def final_section_for(region: str) -> str:
    if region in {"appendix", "post_reference"}:
        return "## 八、参考文献后内容与补充材料"
    return "## 五、图表公式解释"


def required_in_final_for(
    item_type: str,
    region: str,
    confidence_value: str,
    core_level: str = "",
    label: str = "",
) -> bool:
    # Low-confidence items are never required — they need human review first.
    if confidence_value == "low":
        return False
    # Candidate labels (inferred without reliable paper numbering) are not required.
    if "candidate" in label.lower():
        return False
    if SUPPLEMENTARY_LABEL_PREFIX_RE.search(label):
        return False
    # Appendix and post-reference items are supplementary — not required in main body.
    if region in {"appendix", "post_reference"}:
        return False
    # In main region, only core-candidate items with high/medium confidence are required.
    if region == "main":
        if core_level == "core_candidate" and confidence_value in {"high", "medium"}:
            return True
        # High-confidence items in main region are always required.
        if confidence_value == "high":
            return True
        return False
    # Fallback: only require well-typed items with at least medium confidence.
    if confidence_value not in {"high", "medium"}:
        return False
    return item_type in {
        "Figure",
        "Table",
        "Equation",
        "Algorithm",
        "Objective",
        "Loss",
        "Score",
        "Constraint",
        "Prompt",
        "Case Study",
        "Checklist",
    }


def narrative_slots_for(item_type: str) -> list[str]:
    normalized = TYPE_TO_KIND.get(item_type, item_type.lower())
    if normalized == "equation":
        return [
            "what_it_is",
            "symbols",
            "objective_or_constraint",
            "method_position",
            "claim_or_result_connection",
            "failure_boundary",
            "meeting_talk_line",
        ]
    if normalized == "table":
        return [
            "what_it_is",
            "setting_or_columns",
            "strongest_baselines",
            "claim_supported",
            "result_boundary",
            "meeting_talk_line",
        ]
    if normalized == "figure":
        return [
            "what_it_is",
            "mechanism_or_panels",
            "claim_supported",
            "result_boundary",
            "meeting_talk_line",
        ]
    return [
        "what_it_is",
        "why_it_matters",
        "claim_supported",
        "result_boundary",
        "meeting_talk_line",
    ]


def formula_slots_for(item_type: str) -> list[str]:
    if TYPE_TO_KIND.get(item_type, item_type.lower()) != "equation":
        return []
    return [
        "formula_visual_or_latex",
        "symbols",
        "objective_or_constraint",
        "method_position",
        "intuition",
        "claim_or_result_connection",
        "failure_boundary",
    ]


def repair_hint_for(item_type: str) -> str:
    normalized = TYPE_TO_KIND.get(item_type, item_type.lower())
    if normalized == "equation":
        return (
            "Rewrite this Equation/Loss/Objective entry with LaTeX or the formula image, "
            "symbol explanations, optimization/constraint intuition, method position, "
            "claim/result connection, and boundary."
        )
    if normalized == "table":
        return (
            "Rewrite this Table entry as an evidence narrative: explain rows/columns, "
            "metrics, strongest baselines, main gains, tradeoffs, and conclusion boundary."
        )
    if normalized == "figure":
        return (
            "Rewrite this Figure entry as an evidence narrative: explain mechanism or panels, "
            "the claim it supports, and what the figure cannot prove."
        )
    return (
        "Rewrite this evidence entry with what it is, why it matters, which claim it supports, "
        "its boundary, and a concise group-meeting talk line."
    )


def asset_bindings_for(
    asset_paths: list[str],
    asset_hashes: dict[str, str],
    asset_match_status: str,
) -> list[dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    for index, path in enumerate(asset_paths, start=1):
        if asset_match_status == "orphan_formula_candidate":
            confidence_value = "low"
            verification_status = "needs_visual_verification"
            role = "orphan_formula_candidate"
        else:
            confidence_value = "high" if index == 1 else "medium"
            verification_status = "matched"
            role = "main" if index == 1 else "panel"
        bindings.append(
            {
                "source_path": path,
                "sha256": asset_hashes.get(path, ""),
                "confidence": confidence_value,
                "role": role,
                "verification_status": verification_status,
            }
        )
    return bindings


def label_sort_key(label: str) -> str:
    return re.sub(r"\s+", " ", label.strip().lower())


def item_key_for(item_type: str, label: str, region: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", f"{region}-{item_type}-{label}".lower()).strip("-")
    return cleaned or "evidence-item"


def same_page_or_unknown(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_page = str(left.get("page", "") or "")
    right_page = str(right.get("page", "") or "")
    return not left_page or not right_page or left_page == right_page


def build_source_blocks(
    blocks: list[Any], assets_dir: Path | None
) -> tuple[list[dict[str, Any]], int]:
    source_blocks: list[dict[str, Any]] = []
    current_region = "main"
    current_section = "<front matter>"
    seen_references = False
    equation_counters: dict[tuple[str, str, str], int] = {}

    for index, block_value in enumerate(blocks, start=1):
        if not isinstance(block_value, dict):
            continue
        text = block_text(block_value)
        assets = asset_candidates(block_value, assets_dir)
        asset_paths = canonical_asset_paths(assets)
        btype = block_type(block_value).lower()
        labels = filter_contextual_labels(find_labels(text), btype, text)
        text_level = block_value.get("text_level")
        is_heading = (
            "title" in btype
            or "heading" in btype
            or text.startswith("#")
            or (btype == "text" and isinstance(text_level, int) and text_level == 1)
        )

        if text and is_heading:
            current_section = clean_heading(text)
            current_region, seen_references = update_region(text, current_region, seen_references)
            if current_region == "references":
                continue
        elif seen_references and current_region == "references":
            if assets or APPENDIX_RE.search(text) or SPECIAL_RE.search(text):
                current_region = "post_reference"
                current_section = "post-reference supplementary content"
            else:
                continue

        if current_region == "references":
            continue
        if not text and not assets:
            continue
        if not labels:
            labels = infer_equation_labels(
                btype,
                text,
                current_section,
                current_region,
                page_number(block_value),
                equation_counters,
            )

        role = source_role(block_value, text, assets)
        source_blocks.append(
            {
                "position": len(source_blocks),
                "block_index": index,
                "block": block_value,
                "type": btype,
                "section": current_section,
                "region": current_region,
                "page": page_number(block_value),
                "text": text,
                "labels": labels,
                "assets": assets,
                "asset_paths": asset_paths,
                "role": role,
                "content_payload": content_payload(block_value),
            }
        )
    return source_blocks, len(source_blocks)


def nearby_asset_blocks(
    source_blocks: list[dict[str, Any]],
    position: int,
    assigned_asset_blocks: set[int],
    window: int = 6,
) -> list[dict[str, Any]]:
    current = source_blocks[position]
    candidates: list[dict[str, Any]] = []
    for offset in range(-window, window + 1):
        if offset == 0:
            continue
        pos = position + offset
        if pos < 0 or pos >= len(source_blocks):
            continue
        candidate = source_blocks[pos]
        if candidate["block_index"] in assigned_asset_blocks:
            continue
        if not candidate.get("asset_paths"):
            continue
        if candidate.get("labels"):
            continue
        if candidate.get("region") != current.get("region"):
            continue
        if not page_distance_ok(current, candidate):
            continue
        candidates.append(candidate)
    return sorted(candidates, key=lambda item: item["position"])


def has_nearby_explicit_label(
    source_blocks: list[dict[str, Any]],
    position: int,
    window: int = 6,
) -> bool:
    current = source_blocks[position]
    for offset in range(-window, window + 1):
        if offset == 0:
            continue
        pos = position + offset
        if pos < 0 or pos >= len(source_blocks):
            continue
        candidate = source_blocks[pos]
        if not candidate.get("labels"):
            continue
        if candidate.get("region") != current.get("region"):
            continue
        if page_distance_ok(current, candidate):
            return True
    return False


def source_block_summary(block: dict[str, Any], role: str | None = None) -> dict[str, Any]:
    return {
        "block_index": block["block_index"],
        "page": block.get("page", ""),
        "role": role or block.get("role", ""),
        "asset_paths": block.get("asset_paths", []),
        "text": str(block.get("text", ""))[:500],
    }


def expected_kind_for_item(item_type: str) -> str:
    return TYPE_TO_KIND.get(item_type, item_type.lower())


def asset_block_kind(block: dict[str, Any]) -> str:
    kinds = [asset.get("kind", "unknown") for asset in block.get("assets", [])]
    useful = [kind for kind in kinds if kind and kind != "unknown"]
    if not useful:
        return "unknown"
    return useful[0] if len(set(useful)) == 1 else "mixed"


def asset_compatible(item_type: str, asset_block: dict[str, Any]) -> bool:
    expected = expected_kind_for_item(item_type)
    actual = asset_block_kind(asset_block)
    if actual in {"unknown", "mixed"}:
        return True
    if expected == actual:
        return True
    if expected == "figure" and actual in {"image", "unknown"}:
        return True
    return False


def caption_allows_multi_asset(text: str) -> bool:
    lowered = text.lower()
    if re.search(r"\b(left|right|top|bottom|panel|panels|subfigure|subfigures)\b", lowered):
        return True
    if re.search(r"\([a-z]\)|\b[a-z]\)", lowered):
        return True
    return False


def pair_asset_runs(
    source_blocks: list[dict[str, Any]]
) -> dict[int, list[dict[str, Any]]]:
    pairs: dict[int, list[dict[str, Any]]] = {}
    index = 0
    while index < len(source_blocks):
        block = source_blocks[index]
        if block.get("labels") or not block.get("asset_paths"):
            index += 1
            continue
        asset_run: list[dict[str, Any]] = []
        start = index
        while (
            index < len(source_blocks)
            and not source_blocks[index].get("labels")
            and source_blocks[index].get("asset_paths")
        ):
            asset_run.append(source_blocks[index])
            index += 1
        caption_run: list[dict[str, Any]] = []
        caption_index = index
        while (
            caption_index < len(source_blocks)
            and source_blocks[caption_index].get("labels")
            and not source_blocks[caption_index].get("asset_paths")
            and same_page_or_unknown(asset_run[-1], source_blocks[caption_index])
        ):
            caption_run.append(source_blocks[caption_index])
            caption_index += 1
        if asset_run and caption_run:
            if len(caption_run) == 1:
                pairs[caption_run[0]["block_index"]] = list(asset_run)
            else:
                for asset_block, caption_block in zip(asset_run, caption_run):
                    pairs[caption_block["block_index"]] = [asset_block]
        index = max(index, start + 1)
    return pairs


def asset_blocks_for_label(
    labels: list[tuple[str, str]],
    label_index: int,
    label_block: dict[str, Any],
    adjacent_assets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not adjacent_assets:
        return []
    if len(labels) > 1 and len(adjacent_assets) == len(labels):
        return [adjacent_assets[label_index]]
    if len(labels) > 1 and not caption_allows_multi_asset(str(label_block.get("text", ""))):
        return [adjacent_assets[label_index]] if label_index < len(adjacent_assets) else []
    return adjacent_assets


def all_image_files(assets_dir: Path | None) -> list[Path]:
    if not assets_dir or not assets_dir.is_dir():
        return []
    return sorted(
        path.resolve()
        for path in assets_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def latex_complexity(text: str) -> int:
    compact = re.sub(r"\s+", "", text)
    score = len(compact)
    score += 30 * len(re.findall(r"\\frac", compact))
    score += 12 * len(re.findall(r"\\sum|\\prod|\\log|\\exp|\\sigma", compact))
    return score


def source_referenced_asset_paths(source_blocks: list[dict[str, Any]]) -> set[str]:
    paths: set[str] = set()
    for block in source_blocks:
        for raw_path in block.get("asset_paths", []):
            try:
                paths.add(str(Path(raw_path).resolve()))
            except OSError:
                paths.add(str(raw_path))
    return paths


def synthetic_orphan_formula_block(
    equation_block: dict[str, Any],
    asset_path: Path,
    match_reason: str,
) -> dict[str, Any]:
    resolved = str(asset_path.resolve())
    return {
        "position": equation_block.get("position", 0),
        "block_index": f"orphan-formula:{asset_path.name}",
        "block": {},
        "type": "orphan_formula_image",
        "section": equation_block.get("section", ""),
        "region": equation_block.get("region", ""),
        "page": equation_block.get("page", ""),
        "text": match_reason,
        "labels": [],
        "assets": [
            {
                "path": asset_path.name,
                "resolved_path": resolved,
                "exists": "yes",
                "source_key": "orphan_formula_scan",
                "kind": "equation",
            }
        ],
        "asset_paths": [resolved],
        "role": "orphan_formula_object",
        "content_payload": {"orphan_formula_match": match_reason},
    }


def match_orphan_formula_assets(
    source_blocks: list[dict[str, Any]],
    assets_dir: Path | None,
) -> dict[int, list[dict[str, Any]]]:
    referenced = source_referenced_asset_paths(source_blocks)
    candidates = [
        path
        for path in all_image_files(assets_dir)
        if str(path.resolve()) not in referenced and is_likely_formula_image(path)
    ]
    equation_blocks = [
        block
        for block in source_blocks
        if block.get("labels")
        and not block.get("asset_paths")
        and is_equation_block(str(block.get("type", "")), str(block.get("text", "")))
    ]
    if not candidates or not equation_blocks:
        return {}

    # Pair by formula visual width and LaTeX complexity. This is conservative: unmatched
    # candidates remain visible to audit_unmatched_assets.py instead of being invented away.
    pairs: dict[int, list[dict[str, Any]]] = {}
    available = sorted(candidates, key=lambda path: (image_width(path), path.name.lower()))
    ranked_equations = sorted(
        equation_blocks,
        key=lambda block: (latex_complexity(str(block.get("text", ""))), int(block.get("position", 0))),
    )
    if available and ranked_equations:
        avg_width = sum(max(1, image_width(path)) for path in available) / len(available)
        avg_complexity = sum(
            max(1, latex_complexity(str(block.get("text", "")))) for block in ranked_equations
        ) / len(ranked_equations)
        scale = avg_width / avg_complexity if avg_complexity else 1.0
    else:
        scale = 1.0

    used: set[Path] = set()
    for block in ranked_equations:
        if not available:
            break
        expected_width = latex_complexity(str(block.get("text", ""))) * scale
        best = min(
            (path for path in available if path not in used),
            key=lambda path: (
                abs(max(1, image_width(path)) - expected_width),
                path.name.lower(),
            ),
            default=None,
        )
        if best is None:
            continue
        used.add(best)
        reason = (
            "orphan formula image candidate selected by formula-crop shape and LaTeX complexity; "
            "verify visually when preparing the final note"
        )
        pairs[int(block["block_index"])] = [synthetic_orphan_formula_block(block, best, reason)]
    return pairs


def merge_payloads(blocks: list[dict[str, Any]]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for block in blocks:
        for key, value in block.get("content_payload", {}).items():
            if key not in merged:
                merged[key] = value
    return merged


def build_item_from_blocks(
    item_type: str,
    label: str,
    label_block: dict[str, Any],
    asset_blocks: list[dict[str, Any]],
) -> dict[str, Any]:
    own_asset_paths = list(label_block.get("asset_paths", []))
    asset_paths: list[str] = []
    asset_candidates: list[dict[str, str]] = []
    source_blocks = [source_block_summary(label_block)]
    payload_blocks = [label_block]

    for path in own_asset_paths:
        if path not in asset_paths:
            asset_paths.append(path)
    asset_candidates.extend(label_block.get("assets", []))

    unresolved_asset_candidates: list[dict[str, Any]] = []
    compatible_asset_blocks: list[dict[str, Any]] = []
    for asset_block in asset_blocks:
        if asset_compatible(item_type, asset_block):
            compatible_asset_blocks.append(asset_block)
        else:
            unresolved_asset_candidates.append(
                {
                    "block_index": asset_block.get("block_index", ""),
                    "page": asset_block.get("page", ""),
                    "asset_paths": asset_block.get("asset_paths", []),
                    "asset_kind": asset_block_kind(asset_block),
                    "reason": f"asset kind is not compatible with {item_type}",
                }
            )

    for asset_block in compatible_asset_blocks:
        payload_blocks.append(asset_block)
        source_blocks.append(source_block_summary(asset_block, "adjacent_object"))
        asset_candidates.extend(asset_block.get("assets", []))
        for path in asset_block.get("asset_paths", []):
            if path not in asset_paths:
                asset_paths.append(path)

    role = label_block.get("role", "prose_reference")
    has_orphan_formula_asset = any(
        asset_block.get("type") == "orphan_formula_image" for asset_block in compatible_asset_blocks
    )
    core_level, rationale = core_guess(item_type, label_block.get("text", ""), label_block["region"])
    conf, conf_reason = merged_confidence(
        role, label, asset_paths, own_asset_paths, label_block.get("text", "")
    )
    panel_roles = [
        {
            "asset_path": path,
            "asset_index": index,
            "panel": chr(ord("A") + index - 1) if len(asset_paths) > 1 and index <= 26 else str(index),
        }
        for index, path in enumerate(asset_paths, start=1)
    ]
    asset_hashes = {path: file_sha256(path) for path in asset_paths}
    asset_match_status = (
        "orphan_formula_candidate"
        if has_orphan_formula_asset
        else "matched"
        if asset_paths
        else "unresolved_kind_mismatch"
        if unresolved_asset_candidates
        else "missing"
    )
    return {
        "order": 0,
        "source_order_index": 0,
        "item_key": item_key_for(item_type, label, label_block["region"]),
        "type": item_type,
        "item_type": item_type,
        "label": label,
        "display_label": label,
        "normalized_label": label_sort_key(label).replace(" ", "_"),
        "label_key": label_sort_key(label),
        "region": label_block["region"],
        "paper_region": label_block["region"],
        "final_section": final_section_for(label_block["region"]),
        "target_section": final_section_for(label_block["region"]),
        "section": label_block["section"],
        "block_index": label_block["block_index"],
        "page": label_block.get("page", ""),
        "source_role": role,
        "source_text": label_block.get("text", "")[:1200],
        "caption_or_nearby_text": label_block.get("text", "")[:500],
        "source_blocks": source_blocks,
        "content_payload": merge_payloads(payload_blocks),
        "asset_candidates": asset_candidates,
        "asset_paths": asset_paths,
        "asset_hashes": asset_hashes,
        "asset_kind": expected_kind_for_item(item_type),
        "asset_match_status": asset_match_status,
        "asset_bindings": asset_bindings_for(asset_paths, asset_hashes, asset_match_status),
        "unresolved_asset_candidates": unresolved_asset_candidates,
        "panel_roles": panel_roles,
        "matched_asset": asset_paths[0] if asset_paths else "",
        "match_confidence": conf,
        "confidence": conf,
        "required_in_final": required_in_final_for(item_type, label_block["region"], conf, core_level, label),
        "match_reason": (
            conf_reason + "; formula crop came from heuristic orphan image recovery and needs visual verification"
            if has_orphan_formula_asset
            else conf_reason
            if not unresolved_asset_candidates
            else conf_reason + "; incompatible adjacent asset candidates require review"
        ),
        "core_level": core_level,
        "core_rank": "core" if core_level == "core_candidate" else "supporting",
        "rationale": rationale,
        "final_entry_style": "full" if core_level == "core_candidate" else "compressed",
        "required_narrative_slots": narrative_slots_for(item_type),
        "formula_slots": formula_slots_for(item_type),
        "repair_hint": repair_hint_for(item_type),
    }


def merge_items(existing: dict[str, Any], incoming: dict[str, Any]) -> None:
    for path in incoming.get("asset_paths", []):
        if path not in existing["asset_paths"]:
            existing["asset_paths"].append(path)
    existing["matched_asset"] = existing["asset_paths"][0] if existing["asset_paths"] else ""
    existing["asset_hashes"] = {path: file_sha256(path) for path in existing["asset_paths"]}
    existing["asset_bindings"] = asset_bindings_for(
        existing["asset_paths"],
        existing["asset_hashes"],
        existing.get("asset_match_status", "matched"),
    )
    existing["panel_roles"] = [
        {
            "asset_path": path,
            "asset_index": index,
            "panel": chr(ord("A") + index - 1)
            if len(existing["asset_paths"]) > 1 and index <= 26
            else str(index),
        }
        for index, path in enumerate(existing["asset_paths"], start=1)
    ]
    existing["asset_candidates"].extend(incoming.get("asset_candidates", []))
    existing["source_blocks"].extend(incoming.get("source_blocks", []))
    existing.setdefault("unresolved_asset_candidates", []).extend(
        incoming.get("unresolved_asset_candidates", [])
    )
    if existing["asset_paths"]:
        existing["asset_match_status"] = "matched"
        existing["asset_bindings"] = asset_bindings_for(
            existing["asset_paths"],
            existing["asset_hashes"],
            existing["asset_match_status"],
        )
    elif existing.get("unresolved_asset_candidates"):
        existing["asset_match_status"] = "unresolved_kind_mismatch"
    for key, value in incoming.get("content_payload", {}).items():
        existing.setdefault("content_payload", {}).setdefault(key, value)
    if CONFIDENCE_ORDER.get(incoming["match_confidence"], 2) < CONFIDENCE_ORDER.get(
        existing["match_confidence"], 2
    ):
        existing["match_confidence"] = incoming["match_confidence"]
        existing["confidence"] = incoming["confidence"]
        existing["match_reason"] = incoming["match_reason"]


def normalize_item_asset_hashes(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hash_to_canonical: dict[str, str] = {}
    hash_groups: dict[str, set[str]] = {}
    for item in items:
        asset_hashes = item.get("asset_hashes") or {}
        if not isinstance(asset_hashes, dict):
            asset_hashes = {}
        for path in item.get("asset_paths", []):
            file_hash = str(asset_hashes.get(path) or "")
            if not file_hash:
                file_hash = file_sha256(path)
            if not file_hash:
                continue
            hash_to_canonical.setdefault(file_hash, path)
            hash_groups.setdefault(file_hash, set()).add(path)

    for item in items:
        canonical_assets: list[dict[str, Any]] = []
        for path in item.get("asset_paths", []):
            file_hash = str((item.get("asset_hashes") or {}).get(path) or file_sha256(path))
            canonical = hash_to_canonical.get(file_hash, path)
            canonical_assets.append(
                {
                    "asset_path": path,
                    "sha256": file_hash,
                    "canonical_asset_path": canonical,
                    "is_canonical": path == canonical,
                    "duplicate_path_count": len(hash_groups.get(file_hash, set())),
                }
            )
        item["canonical_assets"] = canonical_assets
        if canonical_assets:
            item["canonical_matched_asset"] = canonical_assets[0]["canonical_asset_path"]
    duplicate_groups = [
        {
            "sha256": file_hash,
            "canonical_asset_path": sorted(paths)[0],
            "asset_paths": sorted(paths),
            "path_count": len(paths),
        }
        for file_hash, paths in sorted(hash_groups.items())
        if len(paths) > 1
    ]
    return duplicate_groups


def build_manifest(
    content_list_path: Path,
    assets_dir: Path | None,
    full_md_path: Path | None,
    min_confidence: str = "medium",
    split_regions: bool = False,
) -> dict[str, Any]:
    data = read_json(content_list_path)
    if isinstance(data, list):
        blocks = data
    elif isinstance(data, dict):
        extracted_blocks = data.get("content_list") or data.get("blocks")
        blocks = extracted_blocks if isinstance(extracted_blocks, list) else [data]
    else:
        blocks = []
    if not isinstance(blocks, list):
        blocks = []

    source_blocks, raw_source_block_count = build_source_blocks(blocks, assets_dir)
    run_pairs = pair_asset_runs(source_blocks)
    orphan_formula_pairs = match_orphan_formula_assets(source_blocks, assets_dir)
    items: list[dict[str, Any]] = []
    seen: dict[tuple[str, str, str], dict[str, Any]] = {}
    assigned_asset_blocks: set[int] = set()
    raw_item_count = 0

    for position, source_block in enumerate(source_blocks):
        labels = list(source_block.get("labels") or [])
        if not labels and source_block.get("asset_paths"):
            if has_nearby_explicit_label(source_blocks, position):
                continue
            inferred = infer_label_from_block(source_block["block"], source_block.get("assets", []))
            labels = [inferred] if inferred else []
        if not labels:
            continue

        has_explicit_label = bool(source_block.get("labels"))
        adjacent_assets: list[dict[str, Any]] = []
        if has_explicit_label and source_block["block_index"] in run_pairs:
            adjacent_assets = [
                block
                for block in run_pairs[source_block["block_index"]]
                if block["block_index"] not in assigned_asset_blocks
            ]
        elif has_explicit_label and not source_block.get("asset_paths"):
            adjacent_assets = nearby_asset_blocks(source_blocks, position, assigned_asset_blocks)
        if has_explicit_label and source_block["block_index"] in orphan_formula_pairs:
            adjacent_assets = adjacent_assets + orphan_formula_pairs[source_block["block_index"]]

        for label_index, (item_type, label) in enumerate(labels):
            key = (item_type, label, source_block["region"])
            if key in seen and source_block.get("role") == "prose_reference":
                continue

            asset_blocks = (
                asset_blocks_for_label(labels, label_index, source_block, adjacent_assets)
                if has_explicit_label
                else []
            )
            item = build_item_from_blocks(item_type, label, source_block, asset_blocks)
            raw_item_count += 1

            if key in seen:
                merge_items(seen[key], item)
            else:
                seen[key] = item
                items.append(item)

        if has_explicit_label and adjacent_assets:
            for asset_block in adjacent_assets:
                assigned_asset_blocks.add(asset_block["block_index"])
        elif source_block.get("asset_paths") and labels:
            assigned_asset_blocks.add(source_block["block_index"])

    min_level = CONFIDENCE_ORDER.get(min_confidence, 1)
    filtered_items = [
        item for item in items if CONFIDENCE_ORDER.get(item["match_confidence"], 2) <= min_level
    ]
    for order, item in enumerate(filtered_items, start=1):
        item["order"] = order
        item["source_order_index"] = order
    duplicate_asset_hash_groups = normalize_item_asset_hashes(filtered_items)

    result: dict[str, Any] = {
        "schema_version": "2.0",
        "source": {
            "content_list_path": str(content_list_path),
            "assets_dir": str(assets_dir) if assets_dir else "",
            "full_md_path": str(full_md_path) if full_md_path else "",
        },
        "paper_key": "",
        "title": "",
        "note_path": "",
        "note_assets_dir": "",
        "total_raw_items": raw_item_count,
        "total_items": len(filtered_items),
        "source_block_count": raw_source_block_count,
        "min_confidence": min_confidence,
        "orphan_formula_match_count": sum(len(value) for value in orphan_formula_pairs.values()),
        "duplicate_asset_hash_count": len(duplicate_asset_hash_groups),
        "duplicate_asset_hash_groups": duplicate_asset_hash_groups,
    }
    if split_regions:
        result["main_items"] = [
            item for item in filtered_items if item["region"] == "main"
        ]
        result["post_reference_items"] = [
            item for item in filtered_items if item["region"] in {"appendix", "post_reference"}
        ]
    else:
        result["items"] = filtered_items
    return result


def iter_manifest_items(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if "items" in manifest:
        return list(manifest.get("items", []))
    return list(manifest.get("main_items", [])) + list(manifest.get("post_reference_items", []))


def source_pack_value(source_pack: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = source_pack.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    paths = source_pack.get("paths")
    if isinstance(paths, dict):
        for key in keys:
            value = paths.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def apply_source_pack_metadata(manifest: dict[str, Any], source_pack: dict[str, Any], path: Path) -> None:
    manifest["source_pack_path"] = str(path)
    manifest["paper_key"] = source_pack_value(source_pack, "paper_key", "key", "id")
    manifest["title"] = source_pack_value(source_pack, "title")
    manifest["note_path"] = source_pack_value(source_pack, "note_path", "obsidian_note_path")
    manifest["note_assets_dir"] = source_pack_value(
        source_pack, "note_assets_dir", "assets_dir_for_note"
    )
    manifest.setdefault("source", {})["source_pack_path"] = str(path)


def markdown_table(manifest: dict[str, Any]) -> str:
    header = [
        "# Evidence Manifest",
        "",
        f"content_list_path: {manifest['source']['content_list_path']}",
        f"assets_dir: {manifest['source']['assets_dir'] or '<none>'}",
        f"min_confidence: {manifest.get('min_confidence', 'medium')}",
        "",
        "| order | type | label | final section | region | section | block | page | assets | confidence | role | core | style | rationale |",
        "| ----- | ---- | ----- | ------------- | ------ | ------- | ----- | ---- | ------ | ---------- | ---- | ---- | ----- | --------- |",
    ]
    lines: list[str] = []

    def render_items(items: list[dict[str, Any]], section_title: str | None = None) -> None:
        if section_title:
            lines.append(f"### {section_title}")
        for item in items:
            assets = ", ".join(item.get("asset_paths") or []) or item.get("matched_asset") or "<none>"
            section = str(item["section"]).replace("|", "\\|")
            rationale = str(item["rationale"]).replace("|", "\\|")
            final_section = str(item.get("final_section", "")).replace("|", "\\|")
            lines.append(
                f"| {item['order']} | {item['type']} | {item['label']} | {final_section} | "
                f"{item['region']} | {section} | {item['block_index']} | {item['page'] or '<none>'} | "
                f"{assets} | {item['match_confidence']} | {item['source_role']} | {item['core_level']} | "
                f"{item['final_entry_style']} | {rationale} |"
            )

    if "main_items" in manifest:
        render_items(manifest.get("main_items", []), "Main-paper evidence")
        if manifest.get("post_reference_items"):
            render_items(manifest.get("post_reference_items", []), "Post-reference / appendix evidence")
    else:
        render_items(manifest.get("items", []))

    if not lines:
        lines.append(
            "| <none> | <none> | <none> | <none> | main | <none> | <none> | <none> | "
            "<none> | low | <none> | non_core_candidate | compressed | no evidence items found |"
        )
    return "\n".join(header + lines)


def main() -> int:
    args = parse_args()
    source_pack: dict[str, Any] = {}
    source_pack_path: Path | None = None
    if args.source_pack:
        source_pack_path = Path(args.source_pack).expanduser().resolve()
        source_pack = read_json(source_pack_path)

    content_list_arg = args.content_list or source_pack_value(
        source_pack, "content_list", "content_list_path", "content_list_json"
    )
    assets_arg = args.assets_dir or source_pack_value(
        source_pack, "assets_dir", "assets_source_dir", "parser_assets_dir"
    )
    full_md_arg = args.full_md or source_pack_value(
        source_pack, "source_md", "full_md_path", "full_md"
    )
    if not content_list_arg:
        raise SystemExit("content_list is required unless --source-pack provides it")
    content_list_path = Path(content_list_arg).expanduser().resolve()
    assets_dir = Path(assets_arg).expanduser().resolve() if assets_arg else None
    full_md_path = Path(full_md_arg).expanduser().resolve() if full_md_arg else None
    manifest = build_manifest(
        content_list_path,
        assets_dir,
        full_md_path,
        min_confidence=args.min_confidence,
        split_regions=args.split_regions,
    )
    if source_pack_path:
        apply_source_pack_metadata(manifest, source_pack, source_pack_path)
    output = markdown_table(manifest) if args.markdown else json.dumps(manifest, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).expanduser().resolve().write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
