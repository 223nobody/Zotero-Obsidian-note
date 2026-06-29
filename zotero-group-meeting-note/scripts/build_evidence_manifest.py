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

    for index, block_value in enumerate(blocks, start=1):
        if not isinstance(block_value, dict):
            continue
        text = block_text(block_value)
        assets = asset_candidates(block_value, assets_dir)
        asset_paths = canonical_asset_paths(assets)
        labels = find_labels(text)
        btype = block_type(block_value).lower()
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
    window: int = 3,
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
        if not same_page_or_unknown(current, candidate):
            continue
        candidates.append(candidate)
    return sorted(candidates, key=lambda item: item["position"])


def has_nearby_explicit_label(
    source_blocks: list[dict[str, Any]],
    position: int,
    window: int = 3,
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
        if same_page_or_unknown(current, candidate):
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
    return {
        "order": 0,
        "item_key": item_key_for(item_type, label, label_block["region"]),
        "type": item_type,
        "label": label,
        "label_key": label_sort_key(label),
        "region": label_block["region"],
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
        "asset_hashes": {path: file_sha256(path) for path in asset_paths},
        "asset_kind": expected_kind_for_item(item_type),
        "asset_match_status": "matched"
        if asset_paths
        else "unresolved_kind_mismatch"
        if unresolved_asset_candidates
        else "missing",
        "unresolved_asset_candidates": unresolved_asset_candidates,
        "panel_roles": panel_roles,
        "matched_asset": asset_paths[0] if asset_paths else "",
        "match_confidence": conf,
        "confidence": conf,
        "required_in_final": required_in_final_for(item_type, label_block["region"], conf, core_level, label),
        "match_reason": conf_reason
        if not unresolved_asset_candidates
        else conf_reason + "; incompatible adjacent asset candidates require review",
        "core_level": core_level,
        "rationale": rationale,
        "final_entry_style": "full" if core_level == "core_candidate" else "compressed",
    }


def merge_items(existing: dict[str, Any], incoming: dict[str, Any]) -> None:
    for path in incoming.get("asset_paths", []):
        if path not in existing["asset_paths"]:
            existing["asset_paths"].append(path)
    existing["matched_asset"] = existing["asset_paths"][0] if existing["asset_paths"] else ""
    existing["asset_hashes"] = {path: file_sha256(path) for path in existing["asset_paths"]}
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

    result: dict[str, Any] = {
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
