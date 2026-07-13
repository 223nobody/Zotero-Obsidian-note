#!/usr/bin/env python3
"""Shared gate-report helpers for controlled paper-note delivery."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PASS_STATUS = "pass"
FINAL_PASS_STATUSES = {"pass"}
NON_BLOCKING_STATUSES = {"pass", "skipped"}
REPAIR_STATUSES = {"needs_minor_repair", "needs_major_repair", "needs_regeneration"}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig", errors="ignore"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def file_sha256(path: Path | None) -> str:
    if not path or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def path_fingerprint(path: Path | None) -> str:
    if not path:
        return ""
    if path.is_file():
        return file_sha256(path)
    if not path.is_dir():
        return ""
    digest = hashlib.sha256()
    digest.update(b"dir-v1\0")
    for candidate in sorted(item for item in path.rglob("*") if item.is_file()):
        rel = candidate.relative_to(path).as_posix()
        digest.update(rel.encode("utf-8", errors="surrogateescape"))
        digest.update(b"\0")
        digest.update(file_sha256(candidate).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def has_blocking_problems(report: dict[str, Any]) -> bool:
    for key in ("failed_gates", "errors", "failed_items"):
        value = report.get(key, [])
        if isinstance(value, list) and value:
            return True
    return False


def infer_status(report: dict[str, Any], fallback_status: str = "fail") -> str:
    status = str(report.get("status", "") or "").strip()
    if status:
        if status in NON_BLOCKING_STATUSES and has_blocking_problems(report):
            return fallback_status if fallback_status not in NON_BLOCKING_STATUSES else "fail"
        return status
    if has_blocking_problems(report):
        return "fail"
    return fallback_status


def normalize_report(
    report: dict[str, Any],
    *,
    report_type: str,
    fallback_status: str = "fail",
) -> dict[str, Any]:
    normalized = dict(report)
    normalized["schema_version"] = 2
    normalized["report_type"] = str(normalized.get("report_type") or report_type)
    status = infer_status(normalized, fallback_status)
    normalized["status"] = status
    failed_gates = normalized.get("failed_gates", [])
    if not isinstance(failed_gates, list):
        failed_gates = [str(failed_gates)] if failed_gates else []
    normalized["failed_gates"] = [str(gate) for gate in failed_gates]
    if "problem_count" not in normalized:
        problem_count = len(normalized["failed_gates"])
        if isinstance(normalized.get("errors"), list):
            problem_count += len(normalized["errors"])
        if isinstance(normalized.get("failed_items"), list):
            problem_count += len(normalized["failed_items"])
        normalized["problem_count"] = problem_count
    normalized["ok"] = status == PASS_STATUS and not normalized["failed_gates"]
    return normalized


def artifact_hashes(paths: dict[str, str | Path | None]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for key, raw_path in paths.items():
        if not raw_path:
            continue
        path = Path(str(raw_path)).expanduser().resolve()
        fingerprint = path_fingerprint(path)
        if fingerprint:
            hashes[key] = fingerprint
    return hashes


def attach_input_hashes(
    report: dict[str, Any],
    input_paths: dict[str, str | Path | None],
) -> dict[str, Any]:
    report["input_paths"] = {
        key: str(Path(str(value)).expanduser().resolve())
        for key, value in input_paths.items()
        if value
    }
    report["input_hashes"] = artifact_hashes(input_paths)
    return report


def report_brief(path: Path, report: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": report.get("status", ""),
        "path": str(path),
        "failed_gates": report.get("failed_gates", []),
        "failed_items": report.get("failed_items", []),
        "problem_count": report.get("problem_count", 0),
        "input_hashes": report.get("input_hashes", {}),
    }


def failed_gate_list(reports: dict[str, dict[str, Any]]) -> list[str]:
    gates: list[str] = []
    for name, payload in reports.items():
        status = str(payload.get("status", "") or "")
        if status and status not in NON_BLOCKING_STATUSES:
            gates.append(f"{name}/{status}")
        for gate in payload.get("failed_gates", []) or []:
            gate_text = f"{name}/{gate}" if "/" not in str(gate) else str(gate)
            if gate_text not in gates:
                gates.append(gate_text)
    return gates


def next_action_for_failed_gates(failed_gates: list[str]) -> str:
    failed = set(failed_gates)
    if any("domain" in gate and "paper_type_alignment" in gate for gate in failed):
        return "domain_regeneration"
    if any("asset" in gate for gate in failed):
        return "asset_repair"
    if any("formula_depth" in gate or "evidence_narrative" in gate for gate in failed):
        return "item_patch"
    if any("validation" in gate or "evidence_coverage" in gate for gate in failed):
        return "section_patch"
    if failed:
        return "manual_review_required"
    return "none"


def infer_source_pack_paths(source_pack_path: str | Path | None) -> dict[str, str]:
    if not source_pack_path:
        return {}
    path = Path(str(source_pack_path)).expanduser().resolve()
    if not path.is_file():
        return {}
    try:
        data = read_json(path)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    nested_paths = data.get("paths") if isinstance(data.get("paths"), dict) else {}
    result: dict[str, str] = {}
    fields = {
        "content_list": ("content_list", "content_list_path"),
        "source_assets_dir": ("source_assets_dir", "assets_dir", "mineru_assets_dir"),
        "full_md": ("full_md", "full_md_path", "source_md"),
        "pdf_path": ("pdf_path", "pdf"),
    }
    for target_key, candidates in fields.items():
        for candidate in candidates:
            value = data.get(candidate) or nested_paths.get(candidate)
            if value:
                result[target_key] = resolve_pack_path(value, path)
                break
    return result


def resolve_pack_path(value: str | Path | None, source_pack_path: str | Path | None = None) -> str:
    if not value:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    raw_path = Path(text).expanduser()
    if raw_path.is_absolute():
        return str(raw_path.resolve())
    if source_pack_path:
        base = Path(str(source_pack_path)).expanduser().resolve().parent
        return str((base / raw_path).resolve())
    return str(raw_path.resolve())


def report_status(path_text: str) -> tuple[str, dict[str, Any]]:
    if not path_text:
        return "", {}
    path = Path(path_text).expanduser().resolve()
    if not path.is_file():
        return "missing_report", {}
    try:
        report = read_json(path)
    except Exception as exc:  # noqa: BLE001 - caller should report malformed JSON.
        return f"invalid_json:{exc}", {}
    if not isinstance(report, dict):
        return "invalid_report", {}
    return infer_status(report, "fail"), report


def stale_input_hashes(report: dict[str, Any]) -> list[dict[str, str]]:
    input_hashes = report.get("input_hashes", {})
    input_paths = report.get("input_paths", {})
    stale: list[dict[str, str]] = []
    if not isinstance(input_hashes, dict) or not isinstance(input_paths, dict):
        return stale
    for key, expected in input_hashes.items():
        raw_path = input_paths.get(key)
        if not raw_path:
            continue
        path = Path(str(raw_path)).expanduser().resolve()
        actual = file_sha256(path) if path.is_file() else ""
        if actual != str(expected):
            stale.append(
                {
                    "input": str(key),
                    "path": str(path),
                    "expected_sha256": str(expected),
                    "actual_sha256": actual,
                }
            )
    return stale
