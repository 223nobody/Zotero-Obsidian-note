#!/usr/bin/env python3
"""Smoke-test deterministic helpers for the group-meeting note skill."""

from __future__ import annotations

import json
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

import final_gate_runner
import gate_common


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
BUILD_MANIFEST = SCRIPT_DIR / "build_evidence_manifest.py"
PREPARE_OUTPUT = SCRIPT_DIR / "prepare_output.py"
VALIDATE_NOTE = SCRIPT_DIR / "validate_note.py"
VALIDATE_EVIDENCE = SCRIPT_DIR / "validate_evidence_coverage.py"
AUDIT_QUALITY = SCRIPT_DIR / "audit_note_quality.py"
VALIDATE_DOMAIN = SCRIPT_DIR / "validate_domain_consistency.py"
COLLECT_ASSETS = SCRIPT_DIR / "collect_assets.py"
AUDIT_ASSETS = SCRIPT_DIR / "audit_note_assets.py"
AUDIT_UNMATCHED_ASSETS = SCRIPT_DIR / "audit_unmatched_assets.py"
UPDATE_SIDECAR = SCRIPT_DIR / "update_pipeline_sidecar.py"
VALIDATE_SIDECAR = SCRIPT_DIR / "validate_sidecar.py"
FINAL_GATE_RUNNER = SCRIPT_DIR / "final_gate_runner.py"
CONFLICT_PATTERNS = (r"^<<<<<<< ",)


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, encoding="utf-8", errors="replace")


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def write_png(path: Path, width: int, height: int) -> None:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    raw = b"".join(b"\x00" + (b"\xff\xff\xff" * width) for _ in range(height))
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(payload)


def assert_no_conflict_markers() -> None:
    import re
    checked_suffixes = {".md", ".py", ".yaml", ".yml", ".json"}
    offenders: list[str] = []
    for path in sorted(SKILL_DIR.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in checked_suffixes:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(re.search(pattern, text, re.MULTILINE) for pattern in CONFLICT_PATTERNS):
            offenders.append(str(path.relative_to(SKILL_DIR)))
    assert_true(not offenders, "Conflict markers remain: " + ", ".join(offenders))


def main() -> int:
    assert_no_conflict_markers()
    with tempfile.TemporaryDirectory(prefix="zotero_skill_smoke_") as tmp:
        root = Path(tmp)
        assets = root / "assets"
        assets.mkdir()
        (assets / "figure-1.png").write_bytes(b"figure-one")
        (assets / "figure-2.png").write_bytes(b"figure-two")
        (assets / "table-1.png").write_bytes(b"table-one")
        (assets / "supp-figure-1.png").write_bytes(b"supp-figure-one")
        content_list = root / "content_list.json"
        content_list.write_text(
            json.dumps(
                [
                    {"type": "title", "text": "1 Introduction", "page_idx": 1},
                    {
                        "type": "image",
                        "text": "Figure 1: Method overview and pipeline.",
                        "img_path": "figure-1.png",
                        "page_idx": 2,
                    },
                    {
                        "type": "image",
                        "img_path": "figure-2.png",
                        "page_idx": 3,
                    },
                    {
                        "type": "text",
                        "text": "Figure 2: Distillation dynamics.",
                        "page_idx": 3,
                    },
                    {
                        "type": "table",
                        "text": "Table 1: Main result comparison.",
                        "table_path": "table-1.png",
                        "page_idx": 5,
                    },
                    {"type": "title", "text": "Appendix A Additional Results", "page_idx": 8},
                    {
                        "type": "image",
                        "text": "Figure A1: Appendix diagnostic plot.",
                        "img_path": "figure-1.png",
                        "page_idx": 8,
                    },
                    {"type": "title", "text": "References", "page_idx": 9},
                    {
                        "type": "text",
                        "text": "[1] A citation mentioning Figure 9.",
                        "page_idx": 9,
                    },
                    {
                        "type": "image",
                        "text": "Supplementary Figure 1: Extra failure case.",
                        "img_path": "supp-figure-1.png",
                        "page_idx": 10,
                    },
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        manifest_path = root / "manifest.json"
        manifest_result = run(
            [
                sys.executable,
                str(BUILD_MANIFEST),
                str(content_list),
                "--assets-dir",
                str(assets),
                "--output",
                str(manifest_path),
            ]
        )
        assert_true(manifest_result.returncode == 0, manifest_result.stderr)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        items = manifest["items"]
        labels = [item["label"] for item in items]
        regions = {(item["label"], item["block_index"]): item["region"] for item in items}
        assert_true("Figure 1" in labels, "Figure 1 missing from manifest")
        assert_true("Figure 2" in labels, "Figure 2 missing from manifest")
        assert_true("Figure 2.png" not in labels, "Image-only block leaked filename label")
        assert_true("Table 1" in labels, "Table 1 missing from manifest")
        assert_true("Figure 9" not in labels, "Bibliography mention leaked into manifest")
        assert_true(regions.get(("Figure 1", 2)) == "main", "Figure 1 should be main region")
        assert_true(regions.get(("Table 1", 5)) == "main", "Table 1 should be main region")
        appendix_item = next(item for item in items if item["label"] == "Figure A1")
        assert_true(appendix_item["region"] == "appendix", "Appendix evidence should be appendix region")
        assert_true(
            appendix_item["final_section"] == "## 八、参考文献后内容与补充材料",
            "Appendix evidence should route to supplementary section",
        )
        assert_true(
            any(
                item["label"] == "Supplementary Figure 1"
                and item["region"] == "post_reference"
                for item in items
            ),
            "Post-reference evidence missing",
        )
        assert_true(
            any(item["matched_asset"].endswith("figure-1.png") for item in items),
            "Matched figure asset missing",
        )
        assert_true(
            manifest["duplicate_asset_hash_count"] == 0,
            "distinct smoke assets should not produce duplicate manifest hash groups",
        )
        figure_item = next(item for item in items if item["label"] == "Figure 1")
        assert_true("asset_paths" in figure_item, "asset_paths missing from manifest item")
        assert_true(figure_item["asset_paths"], "asset_paths should include matched assets")
        assert_true("canonical_assets" in figure_item, "canonical_assets missing from manifest item")
        figure_two = next(item for item in items if item["label"] == "Figure 2")
        assert_true(
            any(path.endswith("figure-2.png") for path in figure_two["asset_paths"]),
            "Adjacent image block should be merged into Figure 2",
        )
        assert_true("source_blocks" in figure_two, "source_blocks missing from merged item")
        assert_true("item_key" in figure_two, "item_key missing from merged item")
        assert_true("asset_hashes" in figure_two, "asset_hashes missing from merged item")
        assert_true("source_text" in figure_item, "source_text missing from manifest item")
        assert_true("final_section" in figure_item, "final_section missing from manifest item")
        assert_true("target_section" in figure_item, "target_section missing from manifest item")
        assert_true("required_in_final" in figure_item, "required_in_final missing from manifest item")
        assert_true("page" in figure_item, "page missing from manifest item")
        assert_true("block_index" in figure_item, "block_index missing from manifest item")

        split_manifest = root / "split-manifest.json"
        split_result = run(
            [
                sys.executable,
                str(BUILD_MANIFEST),
                str(content_list),
                "--assets-dir",
                str(assets),
                "--output",
                str(split_manifest),
                "--split-regions",
            ]
        )
        assert_true(split_result.returncode == 0, split_result.stderr)
        split_data = json.loads(split_manifest.read_text(encoding="utf-8"))
        assert_true(
            all(item["region"] == "main" for item in split_data["main_items"]),
            "split manifest main_items should contain only main region",
        )
        assert_true(
            any(item["region"] == "appendix" for item in split_data["post_reference_items"]),
            "split manifest should route appendix items into post_reference_items",
        )

        run_content = root / "run_content_list.json"
        (assets / "figure-3.png").write_bytes(b"fake3")
        (assets / "figure-4.png").write_bytes(b"fake4")
        run_content.write_text(
            json.dumps(
                [
                    {"type": "image", "img_path": "figure-3.png", "page_idx": 6},
                    {"type": "image", "img_path": "figure-4.png", "page_idx": 6},
                    {"type": "text", "text": "Figure 3: First run caption.", "page_idx": 6},
                    {"type": "text", "text": "Figure 4: Second run caption.", "page_idx": 6},
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        run_manifest = root / "run-manifest.json"
        run_result = run(
            [
                sys.executable,
                str(BUILD_MANIFEST),
                str(run_content),
                "--assets-dir",
                str(assets),
                "--output",
                str(run_manifest),
            ]
        )
        assert_true(run_result.returncode == 0, run_result.stderr)
        run_items = json.loads(run_manifest.read_text(encoding="utf-8"))["items"]
        run_map = {item["label"]: [Path(path).name for path in item["asset_paths"]] for item in run_items}
        assert_true(run_map.get("Figure 3") == ["figure-3.png"], "Figure 3 should get only first run asset")
        assert_true(run_map.get("Figure 4") == ["figure-4.png"], "Figure 4 should get only second run asset")

        multi_panel_content = root / "multi-panel-content.json"
        (assets / "figure-5-left.png").write_bytes(b"left")
        (assets / "figure-5-right.png").write_bytes(b"right")
        multi_panel_content.write_text(
            json.dumps(
                [
                    {"type": "image", "img_path": "figure-5-left.png", "page_idx": 7},
                    {"type": "image", "img_path": "figure-5-right.png", "page_idx": 7},
                    {"type": "text", "text": "Figure 5: Left and right panel comparison.", "page_idx": 7},
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        multi_panel_manifest = root / "multi-panel-manifest.json"
        multi_panel_result = run(
            [
                sys.executable,
                str(BUILD_MANIFEST),
                str(multi_panel_content),
                "--assets-dir",
                str(assets),
                "--output",
                str(multi_panel_manifest),
            ]
        )
        assert_true(multi_panel_result.returncode == 0, multi_panel_result.stderr)
        multi_panel_item = json.loads(multi_panel_manifest.read_text(encoding="utf-8"))["items"][0]
        assert_true(
            [Path(path).name for path in multi_panel_item["asset_paths"]]
            == ["figure-5-left.png", "figure-5-right.png"],
            "Single multi-panel caption should keep all adjacent assets",
        )
        assert_true(len(multi_panel_item["panel_roles"]) == 2, "multi-panel item should expose panel roles")

        cross_page_panel_content = root / "cross-page-panel-content.json"
        (assets / "figure-9-left.png").write_bytes(b"left-panel")
        (assets / "figure-9-right.png").write_bytes(b"right-panel")
        cross_page_panel_content.write_text(
            json.dumps(
                [
                    {"type": "text", "text": "Figure 9: Left and right panel comparison.", "page_idx": 10},
                    {"type": "header", "text": "Preprint.", "page_idx": 10},
                    {"type": "page_number", "text": "11", "page_idx": 10},
                    {"type": "chart", "img_path": "figure-9-left.png", "page_idx": 11},
                    {"type": "chart", "img_path": "figure-9-right.png", "page_idx": 11},
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        cross_page_panel_manifest = root / "cross-page-panel-manifest.json"
        cross_page_panel_result = run(
            [
                sys.executable,
                str(BUILD_MANIFEST),
                str(cross_page_panel_content),
                "--assets-dir",
                str(assets),
                "--output",
                str(cross_page_panel_manifest),
            ]
        )
        assert_true(cross_page_panel_result.returncode == 0, cross_page_panel_result.stderr)
        cross_page_item = json.loads(cross_page_panel_manifest.read_text(encoding="utf-8"))["items"][0]
        assert_true(
            [Path(path).name for path in cross_page_item["asset_paths"]]
            == ["figure-9-left.png", "figure-9-right.png"],
            "Figure panels on the following page should be merged into one evidence item",
        )

        equation_orphan_content = root / "equation-orphan-content.json"
        write_png(assets / "formula-crop.png", 360, 80)
        equation_orphan_content.write_text(
            json.dumps(
                [
                    {"type": "title", "text": "Appendix C Diagnostics", "page_idx": 12},
                    {
                        "type": "equation",
                        "text": "$$ b_{i,f}=\\frac{|T_{i,f}|}{\\sum_{f'}|T_{i,f'}|}. $$",
                        "page_idx": 12,
                    },
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        equation_orphan_manifest = root / "equation-orphan-manifest.json"
        equation_orphan_result = run(
            [
                sys.executable,
                str(BUILD_MANIFEST),
                str(equation_orphan_content),
                "--assets-dir",
                str(assets),
                "--output",
                str(equation_orphan_manifest),
            ]
        )
        assert_true(equation_orphan_result.returncode == 0, equation_orphan_result.stderr)
        equation_orphan_item = json.loads(equation_orphan_manifest.read_text(encoding="utf-8"))["items"][0]
        assert_true(equation_orphan_item["label"] == "Equation C1", "Appendix equation should get stable label")
        assert_true(
            equation_orphan_item["asset_match_status"] == "orphan_formula_candidate",
            "Formula orphan crop should be exposed as a visual-verification candidate",
        )
        assert_true(
            equation_orphan_item["asset_paths"]
            and Path(equation_orphan_item["asset_paths"][0]).name == "formula-crop.png",
            "Formula orphan crop should be exposed in asset_paths",
        )

        multi_label_content = root / "multi-label-content.json"
        (assets / "figure-6.png").write_bytes(b"six")
        (assets / "figure-7.png").write_bytes(b"seven")
        multi_label_content.write_text(
            json.dumps(
                [
                    {"type": "image", "img_path": "figure-6.png", "page_idx": 8},
                    {"type": "image", "img_path": "figure-7.png", "page_idx": 8},
                    {
                        "type": "text",
                        "text": "Figure 6: First result. Figure 7: Second result.",
                        "page_idx": 8,
                    },
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        multi_label_manifest = root / "multi-label-manifest.json"
        multi_label_result = run(
            [
                sys.executable,
                str(BUILD_MANIFEST),
                str(multi_label_content),
                "--assets-dir",
                str(assets),
                "--output",
                str(multi_label_manifest),
            ]
        )
        assert_true(multi_label_result.returncode == 0, multi_label_result.stderr)
        multi_label_items = json.loads(multi_label_manifest.read_text(encoding="utf-8"))["items"]
        multi_label_map = {
            item["label"]: [Path(path).name for path in item["asset_paths"]]
            for item in multi_label_items
        }
        assert_true(
            multi_label_map.get("Figure 6") == ["figure-6.png"],
            "First label in a multi-label caption should get first adjacent asset",
        )
        assert_true(
            multi_label_map.get("Figure 7") == ["figure-7.png"],
            "Second label in a multi-label caption should get second adjacent asset",
        )

        bom_content = root / "bom_content_list.json"
        bom_content.write_text(
            json.dumps(
                [
                    {"type": "title", "text": "1 Method", "page_idx": 1},
                    {
                        "type": "table",
                        "text": "Table 9: Main result comparison.",
                        "table_body": "<table><tr><td>not a path</td></tr></table>",
                        "page_idx": 2,
                    },
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8-sig",
        )
        bom_manifest = root / "bom-manifest.json"
        bom_result = run(
            [
                sys.executable,
                str(BUILD_MANIFEST),
                str(bom_content),
                "--assets-dir",
                str(assets),
                "--min-confidence",
                "low",
                "--output",
                str(bom_manifest),
            ]
        )
        assert_true(bom_result.returncode == 0, bom_result.stderr)
        table_item = json.loads(bom_manifest.read_text(encoding="utf-8"))["items"][0]
        assert_true(
            not table_item["asset_paths"],
            "table_body/html content should not be treated as an asset path",
        )

        object_content = root / "object-content-list.json"
        object_content.write_text(
            json.dumps(
                {"type": "image", "text": "Figure 8: Object-shaped content list.", "img_path": "figure-1.png"},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        object_manifest = root / "object-manifest.json"
        object_result = run(
            [
                sys.executable,
                str(BUILD_MANIFEST),
                str(object_content),
                "--assets-dir",
                str(assets),
                "--output",
                str(object_manifest),
            ]
        )
        assert_true(object_result.returncode == 0, object_result.stderr)
        object_items = json.loads(object_manifest.read_text(encoding="utf-8"))["items"]
        assert_true(
            object_items and object_items[0]["label"] == "Figure 8",
            "object-shaped content_list should be treated as a single block",
        )

        note = root / "note.md"
        note.write_text(
            "# Group Meeting Note: Smoke\n\n"
            "## Paper Basic Information\n\nSmoke paper.\n\n"
            "## Core Conclusion\n\n"
            "This note explains the method, evidence, boundary, and discussion.\n\n"
            "## Problem Background And Research Positioning\n\n"
            "The old route lacks a controlled skill gate and source-order evidence binding.\n\n"
            "## Innovation Analysis\n\n"
            "The innovation is a controlled evidence timeline with validation gates.\n\n"
            "## Method Or System Mechanism\n\n"
            "The pipeline builds a manifest, copies assets, writes a note, and validates gates.\n\n"
            "## Figure Table Formula Explanation\n\n"
            "#### Figure 1: Method overview\n\n"
            "![Figure 1](assets/figure-1.png)\n\n"
            "Figure 1 explains the pipeline mechanism and supports the main design claim.\n\n"
            "## Related Work Comparison And Connection\n\n"
            "Compared with loose batch prompting, this route separates drafting and validation.\n\n"
            "## Strengths Limitations And Discussion Questions\n\n"
            "The advantage is traceability. The limitation is that semantic quality still needs review.\n\n"
            "# 组会分享笔记：Smoke\n\n"
            "## 五、图表公式解释\n\n"
            "#### Figure 1：Method overview\n\n"
            "![Figure 1](assets/figure-1.png)\n",
            encoding="utf-8",
        )
        validate_result = run([sys.executable, str(VALIDATE_NOTE), str(note), "--json"])
        assert_true(validate_result.returncode == 0, validate_result.stdout + validate_result.stderr)

        quality_result = run(
            [
                sys.executable,
                str(AUDIT_QUALITY),
                "--note",
                str(note),
                "--evidence-manifest",
                str(manifest_path),
                "--blueprint",
                str(SKILL_DIR / "references" / "blueprint.md"),
                "--json",
            ]
        )
        assert_true(quality_result.returncode != 0, "short smoke note should not pass quality gate")
        quality_data = json.loads(quality_result.stdout)
        assert_true(
            quality_data["status"] in {"needs_minor_repair", "needs_major_repair", "needs_regeneration"},
            "quality audit should return a repair status",
        )
        assert_true(
            len(quality_data.get("repair_plan", [])) >= 1,
            "quality audit should emit concrete repair plan items for low scores",
        )
        assert_true(
            len(quality_data.get("failed_gates", [])) >= 1,
            "quality audit should emit failed_gates for downstream repair routing",
        )

        range_note = root / "quality-range-note.md"
        range_note.write_text(
            "# 组会分享笔记：Range Coverage\n\n"
            "## 论文基本信息\n\n"
            "论文类型：benchmark。\n\n"
            "## 一、核心结论\n\n"
            "这篇论文用 Table 4-6 展示主结果、消融和泛化证据，并说明结论边界。\n\n"
            "## 二、问题背景与研究定位\n\n"
            "旧路线缺少统一评测，本工作定位在评测协议和证据覆盖。\n\n"
            "## 三、创新点分析\n\n"
            "创新点是把检索、重排序和下游执行证据放在同一 benchmark 中分析。\n\n"
            "## 四、方法或系统机制\n\n"
            "机制包含数据构造、标签审核、模型评测和结果分析，输入是任务查询，输出是技能排序和质量指标。\n\n"
            "## 五、图表公式解释\n\n"
            "#### Table 4-6：主结果、消融和分组分析\n\n"
            "Table 4 比较 reranking，Table 5 做遮蔽消融，Table 6 展示类别分组。三者共同支撑 benchmark 证据链。\n\n"
            "## 六、与相关工作的对比与联系\n\n"
            "它区别于普通工具检索 benchmark，因为评测对象是长 skill 文档和可组合任务。\n\n"
            "## 七、优点、局限与讨论问题\n\n"
            "局限是合成查询和真实 agent 流量存在分布差异，讨论点是检索指标是否能代表下游成功。\n",
            encoding="utf-8",
        )
        range_manifest = root / "range-manifest.json"
        range_manifest.write_text(
            json.dumps(
                {
                    "items": [
                        {"label": "Table 4", "required_in_final": True},
                        {"label": "Table 5", "required_in_final": True},
                        {"label": "Table 6", "required_in_final": True},
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        range_result = run(
            [
                sys.executable,
                str(AUDIT_QUALITY),
                "--note",
                str(range_note),
                "--evidence-manifest",
                str(range_manifest),
                "--json",
            ]
        )
        range_data = json.loads(range_result.stdout)
        assert_true(
            range_data["scores"]["evidence_coverage"] == 1.0,
            "quality audit should treat Table 4-6 as covering Table 4, Table 5, and Table 6",
        )

        draft_note = root / "draft-artifacts-note.md"
        draft_note.write_text(
            range_note.read_text(encoding="utf-8") + "\n可复核数字包括：42%。\n",
            encoding="utf-8",
        )
        draft_result = run(
            [
                sys.executable,
                str(AUDIT_QUALITY),
                "--note",
                str(draft_note),
                "--evidence-manifest",
                str(range_manifest),
                "--json",
            ]
        )
        draft_data = json.loads(draft_result.stdout)
        assert_true(
            "draft_artifacts" in draft_data.get("failed_gates", []),
            "quality audit should route leftover draft artifacts to a failed gate",
        )

        math_format_note = root / "math-format-note.md"
        math_format_note.write_text(
            "# 组会分享笔记：Math Formatting\n\n"
            "## 论文基本信息\n\n论文类型：theory。\n\n"
            "## 一、核心结论\n\n"
            "本文讨论策略、约束和能力集合，但草稿把 `\\pi_j`、`c_i`、`Cap_I(s)` 写成了代码格式。"
            "真正的文件名如 `source_pack.json` 和路径 `C:\\Users\\test\\paper.pdf` 不应该被当成数学问题。\n\n"
            "## 二、问题背景与研究定位\n\n旧路线没有区分公式符号和代码标识符。\n\n"
            "## 三、创新点分析\n\n创新点是把数学符号规范化为 LaTeX math。\n\n"
            "## 四、方法或系统机制\n\n机制是扫描 inline code span 并识别 LaTeX 命令、上下标和函数式数学符号。\n\n"
            "## 五、图表公式解释\n\n#### Equation 1：策略约束\n\n"
            "该公式解释策略选择和能力边界，但当前符号格式错误。\n\n"
            "## 六、与相关工作的对比与联系\n\n相关工作通常要求 Markdown 中的公式可被渲染。\n\n"
            "## 七、优点、局限与讨论问题\n\n局限是路径和代码名不能被误杀。\n",
            encoding="utf-8",
        )
        math_format_result = run(
            [
                sys.executable,
                str(AUDIT_QUALITY),
                "--note",
                str(math_format_note),
                "--json",
            ]
        )
        math_format_data = json.loads(math_format_result.stdout)
        assert_true(
            "math_format" in math_format_data.get("failed_gates", []),
            "quality audit should fail math-like code spans",
        )
        assert_true(
            math_format_data.get("summary", {}).get("math_format_issue_count", 0) >= 3,
            "math format gate should catch LaTeX, subscript, and function-like symbols",
        )

        formula_depth_note = root / "formula-depth-note.md"
        formula_depth_note.write_text(
            "# 组会分享笔记：Formula Depth\n\n"
            "## 论文基本信息\n\n论文类型：method。\n\n"
            "## 一、核心结论\n\nEquation 1 是核心目标函数。\n\n"
            "## 二、问题背景与研究定位\n\n旧方法缺少可解释的目标函数。\n\n"
            "## 三、创新点分析\n\n创新点依赖 Equation 1。\n\n"
            "## 四、方法或系统机制\n\n方法通过一个目标函数约束候选选择。\n\n"
            "## 五、图表公式解释\n\n"
            "#### Equation 1：目标函数\n\n"
            "$$\\mathcal{L}=\\sum_i c_i$$\n\n"
            "这是训练目标。\n\n"
            "## 六、与相关工作的对比与联系\n\n相关工作只比较最终分数。\n\n"
            "## 七、优点、局限与讨论问题\n\n局限是公式解释过浅。\n",
            encoding="utf-8",
        )
        formula_manifest = root / "formula-depth-manifest.json"
        formula_manifest.write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "label": "Equation 1",
                            "type": "Equation",
                            "required_in_final": True,
                            "core_level": "core_candidate",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        formula_depth_result = run(
            [
                sys.executable,
                str(AUDIT_QUALITY),
                "--note",
                str(formula_depth_note),
                "--evidence-manifest",
                str(formula_manifest),
                "--json",
            ]
        )
        formula_depth_data = json.loads(formula_depth_result.stdout)
        assert_true(
            "formula_depth" in formula_depth_data.get("failed_gates", []),
            "quality audit should fail shallow formula explanations",
        )

        evidence_narrative_note = root / "evidence-narrative-note.md"
        evidence_narrative_note.write_text(
            "# 组会分享笔记：Evidence Narrative\n\n"
            "## 论文基本信息\n\n论文类型：benchmark。\n\n"
            "## 一、核心结论\n\nFigure 1 和 Table 1 是核心证据。\n\n"
            "## 二、问题背景与研究定位\n\n旧路线缺少证据叙事。\n\n"
            "## 三、创新点分析\n\n创新点需要图表支撑。\n\n"
            "## 四、方法或系统机制\n\n方法流程包含数据、模型和评测。\n\n"
            "## 五、图表公式解释\n\n"
            "#### Figure 1：Overview\n\n"
            "Figure 1 展示整体流程。\n\n"
            "#### Table 1：Main Results\n\n"
            "Table 1 展示主要结果。\n\n"
            "## 六、与相关工作的对比与联系\n\n相关工作缺少统一指标。\n\n"
            "## 七、优点、局限与讨论问题\n\n局限是图表解释太浅。\n",
            encoding="utf-8",
        )
        evidence_narrative_manifest = root / "evidence-narrative-manifest.json"
        evidence_narrative_manifest.write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "label": "Figure 1",
                            "type": "Figure",
                            "required_in_final": True,
                            "core_level": "core_candidate",
                        },
                        {
                            "label": "Table 1",
                            "type": "Table",
                            "required_in_final": True,
                            "core_level": "core_candidate",
                        },
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        evidence_narrative_result = run(
            [
                sys.executable,
                str(AUDIT_QUALITY),
                "--note",
                str(evidence_narrative_note),
                "--evidence-manifest",
                str(evidence_narrative_manifest),
                "--json",
            ]
        )
        evidence_narrative_data = json.loads(evidence_narrative_result.stdout)
        assert_true(
            "evidence_narrative" in evidence_narrative_data.get("failed_gates", []),
            "quality audit should fail caption-like figure/table explanations",
        )
        narrative_failed_items = evidence_narrative_data.get("failed_items", [])
        assert_true(
            any(item.get("diagnostics", {}).get("minimum_hits") for item in narrative_failed_items),
            "quality failed_items should expose threshold diagnostics",
        )

        note.write_text(
            "# 组会分享笔记：Smoke\n\n"
            "## 论文基本信息\n\n"
            "这是一篇用于验证批量受控终稿流水线的 smoke paper，论文类型视为系统/方法类。\n\n"
            "## 一、核心结论\n\n"
            "这篇论文的核心结论是：如果组会笔记要批量生成，就必须把 source pack、evidence manifest、资产迁移、结构校验和质量审稿拆成独立 gate。"
            "Figure 1 给出整体流程，Figure 2 展示蒸馏动态，Table 1 说明主结果比较，Figure A1 和 Supplementary Figure 1 用来验证补充材料路由。"
            "结论成立的边界是：自动 gate 能发现结构和证据问题，但语义深度仍需要 review pass 进行补强。\n\n"
            "## 二、问题背景与研究定位\n\n"
            "旧路线的问题不是单篇写作能力完全失效，而是批量上下文会让多篇论文共享同一套浅层表达。"
            "本文把问题定位在批量生成的控制面：每篇论文都需要独立 source pack，避免跨论文污染；每个图表公式都需要 evidence manifest，避免只靠记忆补写。"
            "因此它属于组会笔记生产流水线的工程化控制问题，而不是重新发明笔记结构模板。\n\n"
            "## 三、创新点分析\n\n"
            "第一，流水线把 evidence manifest 作为写作前的硬约束，确保 Figure/Table/Equation 不会被批量摘要吞掉。"
            "第二，blueprint structure gate 复用现有 blueprint，而不是新建并行结构文件。"
            "第三，quality gate 把章节存在和内容达标分开，能识别只有标题、没有机制解释和结果分析的空心稿。"
            "这些创新点分别由 Figure 1、Table 1 和补充材料路由测试支撑。\n\n"
            "## 四、方法或系统机制\n\n"
            "系统流程是：先检查输入 PDF、full.md、content_list.json 和 assets，再为单篇论文写入 source pack。"
            "随后 build_evidence_manifest.py 生成 Figure/Table/Equation 的顺序化清单，prepare_output.py 复制匹配资产，validate_note.py 和 audit_note_quality.py 分别执行结构/证据/资产和内容深度检查。"
            "这个机制的关键是每篇论文独立运行，主 agent 只汇总 gate 报告和最终交付状态。\n\n"
            "## 五、图表公式解释\n\n"
            "#### Figure 1：Method overview\n\n"
            "![Figure 1](assets/figure-1.png)\n\n"
            "Figure 1 展示主流程：输入材料先被整理为 source pack，再生成 evidence manifest，最后经过结构、证据、资产和质量 gate。"
            "它证明的不是某个模型能力提升，而是批量生产过程可以被拆成可验证的状态机。\n\n"
            "#### Figure 2：Distillation dynamics\n\n"
            "![Figure 2](assets/figure-2.png)\n\n"
            "Figure 2 用来验证相邻图片块与 caption 的绑定逻辑。它说明 manifest 不只记录 label，还要把附近图片合并到同一个证据条目，避免图片被丢到文末资源索引。\n\n"
            "#### Table 1：Main result comparison\n\n"
            "![Table 1](assets/table-1.png)\n\n"
            "Table 1 是主结果比较，重点不是表格本身，而是验证 evidence gate 会要求表格条目出现在终稿中，并在对应位置解释比较对象、指标和结论边界。\n\n"
            "## 六、与相关工作的对比与联系\n\n"
            "相比只依赖 prompt 的批量写作，这条路线更接近可审计的数据处理流水线。"
            "它和普通 Markdown 校验不同，因为它不仅检查链接是否存在，还检查证据是否按原文顺序进入 blueprint 指定章节。"
            "它和人工逐篇修稿也不同，因为它先用 gate 缩小问题范围，再让人工或模型集中修复高风险章节。\n\n"
            "## 七、优点、局限与讨论问题\n\n"
            "优点是可追踪、可复跑、可区分生成成功和质量通过。局限是质量 gate 仍然是启发式，不能替代完整论文阅读。"
            "可以讨论的问题包括：required evidence 的粒度如何设定、低置信度图片是否需要人工核对、以及质量分数是否应该按论文类型调整。\n\n"
            "## 八、参考文献后内容与补充材料\n\n"
            "### Figure A1：Appendix diagnostic plot\n\n"
            "![Figure A1](assets/figure-1.png)\n\n"
            "Figure A1 属于 appendix 证据，不应混入主文证据时间线。它用于验证补充材料必须进入单独章节。\n\n"
            "### Supplementary Figure 1：Extra failure case\n\n"
            "![Supplementary Figure 1](assets/supp-figure-1.png)\n\n"
            "Supplementary Figure 1 属于参考文献后的补充内容，用于说明 post-reference evidence 也要覆盖，但位置应在补充材料章节。\n",
            encoding="utf-8",
        )

        domain_note = root / "domain-note.md"
        domain_note.write_text(
            "# 组会分享笔记：Agent Skill Domain\n\n"
            "## 论文基本信息\n\n"
            "| 项目 | 内容 |\n| --- | --- |\n| 论文类型 | system |\n"
            "| 研究方向 | agent-skill |\n\n"
            "## 一、核心结论\n\n"
            "This system paper studies an agent skill architecture. The skill object is a SKILL.md skill package with tools, prompt snippet, and metadata. "
            "It covers the skill lifecycle from acquisition, retrieval, routing, composition, execution, optimization, evolution, governance, and audit.\n\n"
            "## 二、问题背景与研究定位\n\n"
            "旧路线缺少跨框架 framework 运行时和执行环境分析。本文定位在 skill loading、selection、routing 和 execution stage。\n\n"
            "## 三、创新点分析\n\n"
            "创新点是把 skill artifact 编译成 portable cross-framework package，并通过 Figure 1、Table 1、Equation 1、pass rate、trace coverage 和 ablation 作为证据。\n\n"
            "## 四、方法或系统机制\n\n"
            "系统 pipeline 包含 acquisition、retrieval、composition、execution、maintenance 和 governance。Claude、Codex、Gemini 等框架依赖被分析。\n\n"
            "## 五、图表公式解释\n\n"
            "Figure 1 展示 architecture。Table 1 展示 baseline 对比和指标。Equation 1 表示 score。主实验、消融和验证都绑定到证据。\n\n"
            "## 六、与相关工作的对比与联系\n\n"
            "Compared with tool library retrieval and prompt snippet reuse, this work defines a structured skill package and graph node relation.\n\n"
            "## 七、优点、局限与讨论问题\n\n"
            "局限、边界、失败、假设、不适用前提、威胁、风险和代价都来自特定框架和部署场景。\n",
            encoding="utf-8",
        )
        domain_result = run(
            [
                sys.executable,
                str(VALIDATE_DOMAIN),
                "--note",
                str(domain_note),
                "--json",
            ]
        )
        assert_true(domain_result.returncode == 0, domain_result.stdout + domain_result.stderr)
        domain_data = json.loads(domain_result.stdout)
        assert_true(
            domain_data["detected_domain"] == "agent-skill",
            "domain gate should detect agent-skill smoke note",
        )
        assert_true(
            domain_data["status"] == "pass",
            "domain gate should pass the complete agent-skill smoke note",
        )

        cn_domain_note = root / "domain-cn-skill-file-note.md"
        cn_domain_note.write_text(
            "# 组会分享笔记：Skill File Security\n\n"
            "## 论文基本信息\n\n"
            "| 项目 | 内容 |\n| --- | --- |\n| 论文类型 | benchmark |\n"
            "| 研究方向 | agent-skill security |\n\n"
            "## 一、核心结论\n\n"
            "本文研究技能文件如何成为第三方指令入口。技能文件会在 agent 执行前被加载，进而影响工具调用、权限边界和攻击成功率。\n\n"
            "## 二、问题背景与研究定位\n\n"
            "旧路线只讨论普通 prompt injection，而本文把技能文件、技能库、技能加载和执行阶段作为新的 supply-chain 风险。\n\n"
            "## 三、创新点分析\n\n"
            "创新点是定义技能文件攻击面，并用 Figure 1、Table 1、attack success rate、trace analysis 和 human audit 绑定证据。\n\n"
            "## 四、方法或系统机制\n\n"
            "系统 pipeline 覆盖 skill loading、selection、execution、audit、governance 和安全策略检查。\n\n"
            "## 五、图表公式解释\n\n"
            "Figure 1 展示攻击进入 agent skill lifecycle 的位置。Table 1 展示 benchmark 指标和基线对比。\n\n"
            "## 六、与相关工作的对比与联系\n\n"
            "它和 tool library 安全、prompt injection benchmark、skill ecosystem audit 都相关，但把技能文件作为独立对象。\n\n"
            "## 七、优点、局限与讨论问题\n\n"
            "局限、边界、失败、假设、权限、威胁、风险和代价都来自技能文件被加载后的执行环境。\n",
            encoding="utf-8",
        )
        cn_domain_result = run(
            [
                sys.executable,
                str(VALIDATE_DOMAIN),
                "--note",
                str(cn_domain_note),
                "--json",
            ]
        )
        assert_true(cn_domain_result.returncode == 0, cn_domain_result.stdout + cn_domain_result.stderr)
        cn_domain_data = json.loads(cn_domain_result.stdout)
        assert_true(
            cn_domain_data["checks"]["skill_object_defined"]["pass"],
            "domain gate should accept Chinese skill-file wording as skill object evidence",
        )

        collect_source = root / "collect-source.md"
        collect_source.write_text(
            "# Collect\n\n![first](assets/figure-1.png)\n\n![second](assets/figure-1.png)\n",
            encoding="utf-8",
        )
        collected_assets_dir = root / "collected-assets"
        collect_result = run(
            [
                sys.executable,
                str(COLLECT_ASSETS),
                str(collect_source),
                "--assets-dir",
                str(collected_assets_dir),
                "--json",
            ]
        )
        assert_true(collect_result.returncode == 0, collect_result.stderr)
        collect_data = json.loads(collect_result.stdout)
        assert_true(len(collect_data["copied"]) == 1, "collect_assets should not duplicate same target")
        assert_true(
            len(list(collected_assets_dir.iterdir())) == 1,
            "collect_assets should reuse same-hash assets in destination",
        )

        copy_map = root / "copy-map.json"
        prepared_dir = root / "prepared"
        prepare_result = run(
            [
                sys.executable,
                str(PREPARE_OUTPUT),
                "--article-filename",
                "Smoke Paper",
                "--obsidian-dir",
                str(prepared_dir),
                "--no-zotero-file",
                "--sync-from-manifest",
                str(manifest_path),
                "--copy-map",
                str(copy_map),
            ]
        )
        assert_true(prepare_result.returncode == 0, prepare_result.stderr)
        prepare_data = json.loads(prepare_result.stdout)
        assert_true(prepare_data["copy_map_path"] == str(copy_map.resolve()), "copy map path missing")
        copy_map_data = json.loads(copy_map.read_text(encoding="utf-8"))
        assert_true(copy_map_data["copied_assets"], "copy map should contain copied assets")
        copied_markdown = {item.get("markdown", "") for item in copy_map_data["copied_assets"]}
        assert_true(
            "assets/figure-01-smoke-paper-method-overview-pipeline.png" in copied_markdown,
            "manifest sync should use figure-number-paper-topic asset names",
        )
        assert_true(
            "assets/table-01-smoke-paper-main-result-comparison.png" in copied_markdown,
            "manifest sync should use table-number-paper-topic asset names",
        )
        assert_true(
            "assets/figure-01-smoke-paper-supp-extra-failure-case.png" in copied_markdown,
            "post-reference manifest assets should include supp in the asset name",
        )
        assert_true(
            any(item.get("item_key") == figure_two["item_key"] for item in copy_map_data["copied_assets"]),
            "copy map should preserve manifest item_key",
        )
        rerun_prepare_result = run(
            [
                sys.executable,
                str(PREPARE_OUTPUT),
                "--article-filename",
                "Smoke Paper",
                "--obsidian-dir",
                str(prepared_dir),
                "--no-zotero-file",
                "--sync-from-manifest",
                str(manifest_path),
                "--copy-map",
                str(root / "copy-map-rerun.json"),
            ]
        )
        assert_true(rerun_prepare_result.returncode == 0, rerun_prepare_result.stderr)
        rerun_data = json.loads(rerun_prepare_result.stdout)
        assert_true(
            any(item.get("copy_action") == "reused" for item in rerun_data["copied_assets"]),
            "prepare_output should reuse existing same-hash manifest assets on rerun",
        )

        duplicate_hash_assets = root / "duplicate-hash-assets"
        duplicate_hash_assets.mkdir()
        (duplicate_hash_assets / "figure-a.png").write_bytes(b"same-image-bytes")
        (duplicate_hash_assets / "figure-b.png").write_bytes(b"same-image-bytes")
        duplicate_hash_content = root / "duplicate-hash-content.json"
        duplicate_hash_content.write_text(
            json.dumps(
                [
                    {
                        "type": "image",
                        "text": "Figure 21: First semantic binding.",
                        "img_path": "figure-a.png",
                        "page_idx": 21,
                    },
                    {
                        "type": "image",
                        "text": "Figure 22: Second semantic binding.",
                        "img_path": "figure-b.png",
                        "page_idx": 22,
                    },
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        duplicate_hash_manifest = root / "duplicate-hash-manifest.json"
        duplicate_hash_manifest_result = run(
            [
                sys.executable,
                str(BUILD_MANIFEST),
                str(duplicate_hash_content),
                "--assets-dir",
                str(duplicate_hash_assets),
                "--output",
                str(duplicate_hash_manifest),
            ]
        )
        assert_true(duplicate_hash_manifest_result.returncode == 0, duplicate_hash_manifest_result.stderr)
        duplicate_hash_manifest_data = json.loads(duplicate_hash_manifest.read_text(encoding="utf-8"))
        assert_true(
            duplicate_hash_manifest_data["duplicate_asset_hash_count"] == 1,
            "manifest should report same-content MinerU asset duplicates",
        )
        duplicate_hash_copy_map = root / "duplicate-hash-copy-map.json"
        duplicate_hash_prepared = root / "duplicate-hash-prepared"
        duplicate_hash_prepare_result = run(
            [
                sys.executable,
                str(PREPARE_OUTPUT),
                "--article-filename",
                "Duplicate Hash Paper",
                "--obsidian-dir",
                str(duplicate_hash_prepared),
                "--no-zotero-file",
                "--sync-from-manifest",
                str(duplicate_hash_manifest),
                "--copy-map",
                str(duplicate_hash_copy_map),
            ]
        )
        assert_true(duplicate_hash_prepare_result.returncode == 0, duplicate_hash_prepare_result.stderr)
        duplicate_hash_map = json.loads(duplicate_hash_copy_map.read_text(encoding="utf-8"))
        duplicate_hash_entries = duplicate_hash_map["copied_assets"]
        assert_true(
            len(duplicate_hash_entries) == 2,
            "copy map should preserve both evidence bindings even when the image bytes match",
        )
        duplicate_hash_markdown = {item["markdown"] for item in duplicate_hash_entries}
        assert_true(
            len(duplicate_hash_markdown) == 1,
            "same-hash manifest assets should point to one canonical note asset",
        )
        assert_true(
            any(item["copy_action"] == "reused_by_global_hash" for item in duplicate_hash_entries),
            "second same-hash manifest asset should be globally reused",
        )
        duplicate_hash_files = list((duplicate_hash_prepared / "assets").iterdir())
        assert_true(
            len([path for path in duplicate_hash_files if path.is_file()]) == 1,
            "same-hash manifest assets should create only one physical file",
        )

        nested_assets = assets / "images"
        nested_assets.mkdir()
        (nested_assets / "nested-figure.png").write_bytes(b"nested")
        nested_manifest = root / "nested-manifest.json"
        nested_manifest.write_text(
            json.dumps(
                {
                    "source": {"assets_dir": str(assets)},
                    "items": [
                        {
                            "item_key": "main-figure-figure-10",
                            "label": "Figure 10",
                            "type": "Figure",
                            "region": "main",
                            "match_confidence": "high",
                            "matched_asset": "images/nested-figure.png",
                            "asset_paths": ["images/nested-figure.png"],
                            "source_text": "Figure 10: Nested asset routing.",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        nested_copy_map = root / "nested-copy-map.json"
        nested_prepare_result = run(
            [
                sys.executable,
                str(PREPARE_OUTPUT),
                "--article-filename",
                "Nested Paper",
                "--obsidian-dir",
                str(root / "nested-prepared"),
                "--no-zotero-file",
                "--sync-from-manifest",
                str(nested_manifest),
                "--copy-map",
                str(nested_copy_map),
            ]
        )
        assert_true(nested_prepare_result.returncode == 0, nested_prepare_result.stderr)
        nested_map = json.loads(nested_copy_map.read_text(encoding="utf-8"))
        assert_true(
            nested_map["copied_assets"][0]["source"].endswith("images\\nested-figure.png")
            or nested_map["copied_assets"][0]["source"].endswith("images/nested-figure.png"),
            "manifest sync should preserve nested relative asset paths",
        )

        mineru_figures = assets / "figures"
        mineru_figures.mkdir()
        (mineru_figures / "mineru-hash.jpg").write_bytes(b"mineru")
        mineru_manifest = root / "mineru-layout-manifest.json"
        mineru_manifest.write_text(
            json.dumps(
                {
                    "source": {"assets_dir": str(assets)},
                    "items": [
                        {
                            "item_key": "main-figure-figure-20",
                            "label": "Figure 20",
                            "type": "Figure",
                            "region": "main",
                            "match_confidence": "high",
                            "matched_asset": "images/mineru-hash.jpg",
                            "asset_paths": ["images/mineru-hash.jpg"],
                            "source_text": "Figure 20: MinerU figures directory routing.",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        mineru_copy_map = root / "mineru-layout-copy-map.json"
        mineru_prepare_result = run(
            [
                sys.executable,
                str(PREPARE_OUTPUT),
                "--article-filename",
                "MinerU Layout Paper",
                "--obsidian-dir",
                str(root / "mineru-layout-prepared"),
                "--no-zotero-file",
                "--sync-from-manifest",
                str(mineru_manifest),
                "--copy-map",
                str(mineru_copy_map),
            ]
        )
        assert_true(mineru_prepare_result.returncode == 0, mineru_prepare_result.stderr)
        mineru_map = json.loads(mineru_copy_map.read_text(encoding="utf-8"))
        assert_true(
            mineru_map["copied_assets"]
            and (
                mineru_map["copied_assets"][0]["source"].endswith("figures\\mineru-hash.jpg")
                or mineru_map["copied_assets"][0]["source"].endswith("figures/mineru-hash.jpg")
            ),
            "manifest sync should resolve MinerU images/* entries under assets/figures",
        )

        missing_asset_note = root / "missing-asset-note.md"
        missing_asset_note.write_text("# Test\n\n#### Figure 1\n\nText only.\n", encoding="utf-8")
        coverage_manifest = root / "coverage-manifest.json"
        coverage_manifest.write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "label": "Figure 1",
                            "region": "main",
                            "section": "Method",
                            "match_confidence": "high",
                            "matched_asset": str(assets / "figure-1.png"),
                            "asset_paths": [str(assets / "figure-1.png")],
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8-sig",
        )
        coverage_result = run(
            [
                sys.executable,
                str(VALIDATE_NOTE),
                str(missing_asset_note),
                "--evidence-manifest",
                str(coverage_manifest),
                "--json",
            ]
        )
        assert_true(coverage_result.returncode == 0, coverage_result.stdout + coverage_result.stderr)
        coverage = json.loads(coverage_result.stdout)
        assert_true(
            any(w["kind"] == "missing_evidence_asset_link" for w in coverage["warnings"]),
            "validate_note should warn when a high-confidence manifest asset is not linked",
        )

        partial_panel_note = root / "partial-panel-note.md"
        partial_panel_note.write_text(
            "# Test\n\n#### Figure 2\n\n![Only one panel](assets/figure-1.png)\n",
            encoding="utf-8",
        )
        partial_panel_manifest = root / "partial-panel-manifest.json"
        partial_panel_manifest.write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "label": "Figure 2",
                            "type": "Figure",
                            "region": "main",
                            "section": "Method",
                            "match_confidence": "high",
                            "matched_asset": str(assets / "figure-1.png"),
                            "asset_paths": [str(assets / "figure-1.png"), str(assets / "figure-2.png")],
                            "asset_hashes": {
                                str(assets / "figure-1.png"): "",
                                str(assets / "figure-2.png"): "",
                            },
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        partial_panel_result = run(
            [
                sys.executable,
                str(VALIDATE_NOTE),
                str(partial_panel_note),
                "--evidence-manifest",
                str(partial_panel_manifest),
                "--strict-evidence",
                "--json",
            ]
        )
        assert_true(
            partial_panel_result.returncode != 0,
            "Strict evidence validation should fail when a multi-panel item links only one asset",
        )
        partial_panel_data = json.loads(partial_panel_result.stdout)
        assert_true(
            any(e["kind"] == "missing_evidence_asset_link" for e in partial_panel_data["errors"]),
            "Strict evidence validation should report the missing panel asset",
        )

        evidence_gate_result = run(
            [
                sys.executable,
                str(VALIDATE_EVIDENCE),
                "--note",
                str(missing_asset_note),
                "--evidence-manifest",
                str(coverage_manifest),
                "--strict",
                "--json",
            ]
        )
        assert_true(evidence_gate_result.returncode != 0, "strict evidence gate should fail missing assets")

        wrong_placement_note = root / "wrong-placement-note.md"
        wrong_placement_note.write_text(
            "# Test\n\n"
            "## Figure 1\n\nText only.\n\n"
            "## Figure 2\n\n![Figure 1 misplaced](assets/figure-1.png)\n",
            encoding="utf-8",
        )
        wrong_placement_result = run(
            [
                sys.executable,
                str(VALIDATE_NOTE),
                str(wrong_placement_note),
                "--evidence-manifest",
                str(coverage_manifest),
                "--strict-evidence",
                "--json",
            ]
        )
        assert_true(
            wrong_placement_result.returncode != 0,
            "Strict evidence validation should fail misplaced assets",
        )
        wrong_placement = json.loads(wrong_placement_result.stdout)
        assert_true(
            any(e["kind"] == "misplaced_evidence_asset_link" for e in wrong_placement["errors"]),
            "Strict evidence validation should report misplaced evidence asset",
        )

        early_mention_note = root / "early-mention-note.md"
        early_mention_note.write_text(
            "# Test\n\n"
            "## 一、核心结论\n\nFigure 1 summarizes the method.\n\n"
            "## 五、图表公式解释\n\n"
            "### Figure 1 方法总览\n\n"
            "![Figure 1](assets/figure-1.png)\n",
            encoding="utf-8",
        )
        early_result = run(
            [
                sys.executable,
                str(VALIDATE_NOTE),
                str(early_mention_note),
                "--evidence-manifest",
                str(coverage_manifest),
                "--strict-evidence",
                "--json",
            ]
        )
        assert_true(early_result.returncode == 0, early_result.stdout + early_result.stderr)

        duplicate_region_note = root / "duplicate-region-note.md"
        duplicate_region_note.write_text(
            "# Test\n\n"
            "## 五、图表公式解释\n\n"
            "#### Figure 10：Main evidence\n\n"
            "![Figure 10 main](assets/figure-1.png)\n\n"
            "## 八、参考文献后内容与补充材料\n\n"
            "### Figure 10：Supplement evidence\n\n"
            "![Figure 10 supplement](assets/figure-2.png)\n",
            encoding="utf-8",
        )
        duplicate_region_manifest = root / "duplicate-region-manifest.json"
        duplicate_region_manifest.write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "item_key": "main-figure-figure-10",
                            "label": "Figure 10",
                            "type": "Figure",
                            "region": "main",
                            "section": "Method",
                            "match_confidence": "high",
                            "matched_asset": str(assets / "figure-1.png"),
                            "asset_paths": [str(assets / "figure-1.png")],
                        },
                        {
                            "item_key": "post-reference-figure-figure-10",
                            "label": "Figure 10",
                            "type": "Figure",
                            "region": "post_reference",
                            "section": "Appendix",
                            "match_confidence": "high",
                            "matched_asset": str(assets / "figure-2.png"),
                            "asset_paths": [str(assets / "figure-2.png")],
                        },
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        duplicate_region_result = run(
            [
                sys.executable,
                str(VALIDATE_NOTE),
                str(duplicate_region_note),
                "--evidence-manifest",
                str(duplicate_region_manifest),
                "--strict-evidence",
                "--json",
            ]
        )
        assert_true(
            duplicate_region_result.returncode == 0,
            "validate_note should match duplicate labels by main vs supplementary region",
        )

        authoritative_note = root / "authoritative-note.md"
        authoritative_note.write_text(
            "# Test\n\n## Figure 1\n\n![Old link](assets/figure-1.png)\n",
            encoding="utf-8",
        )
        authoritative_map = root / "authoritative-copy-map.json"
        authoritative_map.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "copied_assets": [
                        {
                            "item_key": "main-figure-figure-1",
                            "label": "Figure 1",
                            "markdown": "assets/copied-figure-1.png",
                            "source": str(assets / "figure-1.png"),
                            "destination": str(root / "assets" / "copied-figure-1.png"),
                            "source_sha256": "",
                            "destination_sha256": "",
                        }
                    ],
                    "items": {
                        "main-figure-figure-1": [
                            {
                                "item_key": "main-figure-figure-1",
                                "label": "Figure 1",
                                "markdown": "assets/copied-figure-1.png",
                                "source": str(assets / "figure-1.png"),
                                "destination": str(root / "assets" / "copied-figure-1.png"),
                                "source_sha256": "",
                                "destination_sha256": "",
                            }
                        ]
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        authoritative_manifest = root / "authoritative-manifest.json"
        authoritative_manifest.write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "item_key": "main-figure-figure-1",
                            "label": "Figure 1",
                            "region": "main",
                            "section": "Method",
                            "match_confidence": "high",
                            "matched_asset": str(assets / "figure-1.png"),
                            "asset_paths": [str(assets / "figure-1.png")],
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        authoritative_result = run(
            [
                sys.executable,
                str(VALIDATE_NOTE),
                str(authoritative_note),
                "--evidence-manifest",
                str(authoritative_manifest),
                "--copy-map",
                str(authoritative_map),
                "--copy-map-authoritative",
                "--strict-evidence",
                "--json",
            ]
        )
        assert_true(
            authoritative_result.returncode != 0,
            "Authoritative copy-map validation should reject old non-copy-map links",
        )

        copied_asset = root / "assets" / "copied-figure-1.png"
        copied_asset.write_bytes((assets / "figure-1.png").read_bytes())
        authoritative_ok_note = root / "authoritative-ok-note.md"
        authoritative_ok_note.write_text(
            "# Test\n\n## Figure 1\n\n![Copied link](assets/copied-figure-1.png)\n",
            encoding="utf-8",
        )
        authoritative_ok_result = run(
            [
                sys.executable,
                str(VALIDATE_NOTE),
                str(authoritative_ok_note),
                "--evidence-manifest",
                str(authoritative_manifest),
                "--copy-map",
                str(authoritative_map),
                "--copy-map-authoritative",
                "--strict-evidence",
                "--json",
            ]
        )
        assert_true(
            authoritative_ok_result.returncode == 0,
            authoritative_ok_result.stdout + authoritative_ok_result.stderr,
        )
        authoritative_missing_map_result = run(
            [
                sys.executable,
                str(VALIDATE_NOTE),
                str(authoritative_ok_note),
                "--evidence-manifest",
                str(authoritative_manifest),
                "--copy-map-authoritative",
                "--strict-evidence",
                "--json",
            ]
        )
        assert_true(
            authoritative_missing_map_result.returncode != 0,
            "Authoritative copy-map validation should require --copy-map",
        )
        authoritative_missing_map = json.loads(authoritative_missing_map_result.stdout)
        assert_true(
            any(e["kind"] == "copy_map_required" for e in authoritative_missing_map["errors"]),
            "Authoritative copy-map validation should report missing --copy-map",
        )

        duplicate = assets / "figure-1-copy.png"
        duplicate.write_bytes((assets / "figure-1.png").read_bytes())
        asset_report = root / "asset-report.json"
        audit_result = run(
            [
                sys.executable,
                str(AUDIT_ASSETS),
                str(note),
                "--output",
                str(asset_report),
            ]
        )
        assert_true(audit_result.returncode == 0, audit_result.stderr)
        audit = json.loads(asset_report.read_text(encoding="utf-8"))
        assert_true(audit["status"] == "pass", "asset audit should expose pass status")
        assert_true(audit["report_type"] == "asset", "asset audit should expose report_type")
        assert_true(audit["image_link_count"] >= 1, "asset audit image count mismatch")
        assert_true(audit["assets_total"] >= 5, "asset audit total asset count mismatch")
        assert_true(audit["unused_assets_count"] >= 4, "asset audit unused count mismatch")
        assert_true(audit["duplicate_hash_count"] >= 1, "asset audit duplicate hash missing")
        strict_duplicate_report = root / "asset-strict-duplicate-report.json"
        strict_duplicate_result = run(
            [
                sys.executable,
                str(AUDIT_ASSETS),
                str(note),
                "--output",
                str(strict_duplicate_report),
                "--fail-on-duplicates",
            ]
        )
        assert_true(
            strict_duplicate_result.returncode != 0,
            "asset audit should fail when duplicate hashes remain under --fail-on-duplicates",
        )
        strict_duplicate = json.loads(strict_duplicate_report.read_text(encoding="utf-8"))
        assert_true(strict_duplicate["status"] == "fail", "strict duplicate audit should expose fail status")
        assert_true(
            "duplicate_asset_hashes" in strict_duplicate.get("failed_gates", []),
            "asset audit should report duplicate_asset_hashes failed gate",
        )
        cleanup_report = root / "asset-cleanup-report.json"
        cleanup_result = run(
            [
                sys.executable,
                str(AUDIT_ASSETS),
                str(note),
                "--output",
                str(cleanup_report),
                "--delete-duplicate-unused",
            ]
        )
        assert_true(cleanup_result.returncode == 0, cleanup_result.stderr)
        cleanup = json.loads(cleanup_report.read_text(encoding="utf-8"))
        assert_true(cleanup["deleted_assets"], "asset cleanup should delete unused duplicate assets")
        assert_true("skipped_delete_paths" in cleanup, "asset cleanup should report skipped delete paths")

        unmatched_src = root / "unmatched-src" / "figures"
        unmatched_src.mkdir(parents=True)
        unmatched_final = root / "unmatched-final"
        unmatched_final.mkdir()
        write_png(unmatched_src / "orphan-formula.png", 360, 80)
        write_png(unmatched_src / "figure-panel.png", 420, 260)
        unmatched_content = root / "unmatched-content.json"
        unmatched_content.write_text(
            json.dumps(
                [
                    {"type": "text", "text": "Figure 1: A two-panel figure.", "page_idx": 1},
                    {"type": "chart", "img_path": "images/figure-panel.png", "page_idx": 2},
                    {
                        "type": "equation",
                        "text": "$$ \\mathcal{L}=-\\log p(y|x) $$",
                        "page_idx": 3,
                    },
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        unmatched_report = root / "unmatched-report.json"
        unmatched_result = run(
            [
                sys.executable,
                str(AUDIT_UNMATCHED_ASSETS),
                "--content-list",
                str(unmatched_content),
                "--source-assets-dir",
                str(unmatched_src),
                "--note-assets-dir",
                str(unmatched_final),
                "--output",
                str(unmatched_report),
                "--fail-on-problem-assets",
            ]
        )
        assert_true(
            unmatched_result.returncode != 0,
            "unmatched asset audit should fail formula or structured panel omissions",
        )
        unmatched = json.loads(unmatched_report.read_text(encoding="utf-8"))
        assert_true(unmatched["status"] == "fail", "unmatched asset audit should expose fail status")
        assert_true(unmatched["report_type"] == "unmatched_asset", "unmatched audit should expose report_type")
        assert_true(
            unmatched["classification_counts"].get("formula_orphan_missing", 0) == 1,
            "unmatched audit should classify formula orphan crops",
        )
        assert_true(
            unmatched["classification_counts"].get("structured_figure_or_panel_missing", 0) == 1,
            "unmatched audit should classify structured figure/panel omissions",
        )

        wiki_note = root / "wiki-note.md"
        wiki_note.write_text("# Wiki\n\nNo local image.\n", encoding="utf-8")
        wiki_sibling = root / "wiki-sibling.md"
        wiki_sibling.write_text("# Sibling\n\n![[assets/figure-1.png]]\n", encoding="utf-8")
        wiki_report = root / "wiki-asset-report.json"
        wiki_result = run(
            [
                sys.executable,
                str(AUDIT_ASSETS),
                str(wiki_note),
                "--output",
                str(wiki_report),
                "--scan-sibling-notes",
                "--vault-root",
                str(root),
            ]
        )
        assert_true(wiki_result.returncode == 0, wiki_result.stderr)
        wiki_audit = json.loads(wiki_report.read_text(encoding="utf-8"))
        assert_true(
            wiki_audit["sibling_referenced_assets_count"] >= 1,
            "asset audit should detect sibling wiki embeds",
        )

        sidecar = root / "sidecar.json"
        sidecar_result = run(
            [
                sys.executable,
                str(UPDATE_SIDECAR),
                "--sidecar",
                str(sidecar),
                "--paper-key",
                "smoke-paper",
                "--pdf-path",
                str(root / "paper.pdf"),
                "--source-md",
                str(root / "full.md"),
                "--content-list",
                str(content_list),
                "--manifest-path",
                str(manifest_path),
                "--note-path",
                str(note),
                "--asset-report-path",
                str(asset_report),
                "--stage",
                "validate",
                "--status",
                "complete",
                "--set",
                "counts.image_link_count=1",
            ]
        )
        assert_true(sidecar_result.returncode == 0, sidecar_result.stderr)
        sidecar_data = json.loads(sidecar.read_text(encoding="utf-8"))
        assert_true(sidecar_data["paper_key"] == "smoke-paper", "sidecar paper_key missing")
        assert_true(
            sidecar_data["stages"]["validate"]["status"] == "complete",
            "sidecar validate stage missing",
        )
        assert_true(
            sidecar_data["counts"]["image_link_count"] == 1,
            "sidecar dotted count update missing",
        )
        assert_true(sidecar_data["schema_version"] == 2, "sidecar should migrate to schema v2")
        sidecar_validate_result = run(
            [
                sys.executable,
                str(VALIDATE_SIDECAR),
                str(sidecar),
                "--write-migrated",
                "--json",
            ]
        )
        assert_true(sidecar_validate_result.returncode == 0, sidecar_validate_result.stdout)
        sidecar_validate = json.loads(sidecar_validate_result.stdout)
        assert_true(sidecar_validate["status"] == "pass", "sidecar validator should pass basic sidecar")

        final_gate_report = root / "final-gate.json"
        final_gate_sidecar = root / "final-gate-sidecar.json"
        final_gate_result = run(
            [
                sys.executable,
                str(FINAL_GATE_RUNNER),
                "--paper-key",
                "smoke-paper",
                "--note",
                str(note),
                "--evidence-manifest",
                str(manifest_path),
                "--content-list",
                str(content_list),
                "--source-assets-dir",
                str(assets),
                "--note-assets-dir",
                str(assets),
                "--reports-dir",
                str(root / "final-gate-reports"),
                "--output",
                str(final_gate_report),
                "--sidecar",
                str(final_gate_sidecar),
                "--strict-evidence",
                "--json",
            ]
        )
        assert_true(final_gate_report.is_file(), final_gate_result.stdout + final_gate_result.stderr)
        final_gate = json.loads(final_gate_report.read_text(encoding="utf-8"))
        assert_true(final_gate["schema_version"] == 2, "final gate report should use schema v2")
        assert_true(
            "note" in final_gate.get("input_hashes", {}),
            "final gate report should record note input hash",
        )
        assert_true(
            set(final_gate.get("reports", {})) >= {"validation", "quality", "domain", "asset", "unmatched_asset"},
            "final gate runner should emit all gate report summaries",
        )
        assert_true(
            "input_hashes" in final_gate["reports"]["validation"],
            "final gate report summaries should expose per-report input hashes",
        )
        assert_true(
            final_gate.get("status") in {"pass", "fail"},
            "final gate runner should expose pass/fail status",
        )
        false_pass_stdout = final_gate_runner.report_from_stdout(
            subprocess.CompletedProcess(
                args=["fake-validation"],
                returncode=7,
                stdout=json.dumps({"status": "pass", "failed_gates": []}),
                stderr="forced failure",
            ),
            "fail",
            "validation",
            {"note": note},
        )
        assert_true(
            false_pass_stdout["status"] == "fail",
            "stdout report with failing command return code must not stay pass",
        )
        assert_true(
            "command_failed" in false_pass_stdout.get("failed_gates", []),
            "stdout report should record command_failed",
        )

        false_pass_file = root / "false-pass-file.json"
        false_pass_writer = root / "false-pass-writer.py"
        false_pass_writer.write_text(
            "import json, sys\n"
            "from pathlib import Path\n"
            "Path(sys.argv[1]).write_text("
            "json.dumps({'status': 'pass', 'failed_gates': []}), encoding='utf-8')\n"
            "sys.exit(7)\n",
            encoding="utf-8",
        )
        false_file_ok, false_file_report = final_gate_runner.run_file_report(
            [sys.executable, str(false_pass_writer), str(false_pass_file)],
            false_pass_file,
            "asset",
            {"note": note},
        )
        assert_true(
            not false_file_ok and false_file_report["status"] == "fail",
            "file report with failing command return code must not stay pass",
        )
        assert_true(
            "command_failed" in false_file_report.get("failed_gates", []),
            "file report should record command_failed",
        )
        sidecar_update_failed = False
        try:
            final_gate_runner.update_sidecar(
                str(root),
                stage="final_delivery",
                status="pass",
                message="should fail because path is a directory",
            )
        except RuntimeError:
            sidecar_update_failed = True
        assert_true(sidecar_update_failed, "final gate runner should not ignore sidecar update failures")

        stale_note = root / "stale-note.md"
        stale_note.write_text("# stale\n\nfirst version\n", encoding="utf-8")
        stale_report = root / "stale-pass-report.json"
        stale_report.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "report_type": "validation",
                    "status": "pass",
                    "ok": True,
                    "failed_gates": [],
                    "input_paths": {"note": str(stale_note)},
                    "input_hashes": {"note": "0" * 64},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        stale_final_report = root / "stale-final-gate.json"
        stale_final_report.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "report_type": "final_gate",
                    "status": "pass",
                    "ok": True,
                    "failed_gates": [],
                    "input_paths": {"note": str(stale_note)},
                    "input_hashes": {"note": "0" * 64},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        stale_sidecar = root / "stale-sidecar.json"
        stale_sidecar.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "paper_key": "stale-smoke",
                    "paths": {
                        "note_path": str(stale_note),
                        "validation_report_path": str(stale_report),
                        "quality_report_path": str(stale_report),
                        "domain_report_path": str(stale_report),
                        "asset_report_path": str(stale_report),
                    },
                    "stages": {"final_delivery": {"status": "complete"}},
                    "final_status": "pass",
                    "final_gate_report_path": str(stale_final_report),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        stale_validate_result = run(
            [sys.executable, str(VALIDATE_SIDECAR), str(stale_sidecar), "--json"]
        )
        assert_true(
            stale_validate_result.returncode != 0,
            "sidecar validator should fail stale gate reports",
        )
        stale_validate = json.loads(stale_validate_result.stdout)
        assert_true(
            any(error.get("kind") == "stale_gate_report" for error in stale_validate.get("errors", [])),
            "sidecar validator should report stale_gate_report",
        )

        contradictory_report = root / "contradictory-pass-report.json"
        contradictory_report.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "report_type": "validation",
                    "status": "pass",
                    "ok": False,
                    "failed_gates": ["synthetic_failure"],
                    "input_paths": {"note": str(note)},
                    "input_hashes": {"note": gate_common.file_sha256(note)},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        contradictory_final_gate = root / "contradictory-final-gate.json"
        contradictory_final_gate.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "report_type": "final_gate",
                    "paper_key": "contradictory-smoke",
                    "note": str(note),
                    "status": "pass",
                    "ok": True,
                    "failed_gates": [],
                    "input_paths": {"note": str(note)},
                    "input_hashes": {"note": gate_common.file_sha256(note)},
                    "reports": {
                        gate: {"status": "pass", "path": str(contradictory_report), "failed_gates": []}
                        for gate in ("validation", "quality", "domain", "asset")
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        contradictory_sidecar = root / "contradictory-sidecar.json"
        contradictory_sidecar.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "paper_key": "contradictory-smoke",
                    "paths": {
                        "note_path": str(note),
                        "validation_report_path": str(contradictory_report),
                        "quality_report_path": str(contradictory_report),
                        "domain_report_path": str(contradictory_report),
                        "asset_report_path": str(contradictory_report),
                    },
                    "stages": {"final_delivery": {"status": "complete"}},
                    "final_status": "pass",
                    "final_gate_report_path": str(contradictory_final_gate),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        contradictory_validate_result = run(
            [sys.executable, str(VALIDATE_SIDECAR), str(contradictory_sidecar), "--json"]
        )
        assert_true(
            contradictory_validate_result.returncode != 0,
            "sidecar validator should reject pass reports with failed_gates",
        )

        dir_hash_report = gate_common.attach_input_hashes({}, {"assets": assets})
        old_dir_hash = dir_hash_report["input_hashes"]["assets"]
        (assets / "directory-hash-probe.png").write_bytes(b"directory hash changed")
        dir_staleness = gate_common.stale_input_hashes(dir_hash_report)
        assert_true(old_dir_hash, "directory input hash should be recorded")
        assert_true(
            any(item.get("input") == "assets" for item in dir_staleness),
            "directory input hash should become stale when files change",
        )

        other_note = root / "other-note.md"
        other_note.write_text("# Other\n", encoding="utf-8")
        cross_note_report = root / "cross-note-pass-report.json"
        cross_note_report.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "report_type": "validation",
                    "status": "pass",
                    "ok": True,
                    "failed_gates": [],
                    "input_paths": {"note": str(note)},
                    "input_hashes": {"note": gate_common.file_sha256(note)},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        cross_note_final_gate = root / "cross-note-final-gate.json"
        cross_note_final_gate.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "report_type": "final_gate",
                    "paper_key": "other-smoke",
                    "note": str(other_note),
                    "status": "pass",
                    "ok": True,
                    "failed_gates": [],
                    "input_paths": {"note": str(other_note)},
                    "input_hashes": {"note": gate_common.file_sha256(other_note)},
                    "reports": {
                        gate: {"status": "pass", "path": str(cross_note_report), "failed_gates": []}
                        for gate in ("validation", "quality", "domain", "asset")
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        cross_note_sidecar = root / "cross-note-sidecar.json"
        cross_note_sidecar.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "paper_key": "original-smoke",
                    "paths": {
                        "note_path": str(note),
                        "validation_report_path": str(cross_note_report),
                        "quality_report_path": str(cross_note_report),
                        "domain_report_path": str(cross_note_report),
                        "asset_report_path": str(cross_note_report),
                    },
                    "stages": {"final_delivery": {"status": "complete"}},
                    "final_status": "pass",
                    "final_gate_report_path": str(cross_note_final_gate),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        cross_note_validate_result = run(
            [sys.executable, str(VALIDATE_SIDECAR), str(cross_note_sidecar), "--json"]
        )
        assert_true(
            cross_note_validate_result.returncode != 0,
            "sidecar validator should reject final-gate reports for another note/paper",
        )
        cross_note_validate = json.loads(cross_note_validate_result.stdout)
        cross_note_error_kinds = {error.get("kind") for error in cross_note_validate.get("errors", [])}
        assert_true(
            {"final_gate_note_mismatch", "final_gate_paper_key_mismatch"} & cross_note_error_kinds,
            "sidecar validator should report final-gate identity mismatch",
        )

        empty_batch = root / "empty-batch.json"
        empty_batch.write_text('{"papers":[{}]}', encoding="utf-8-sig")
        batch_result = run(
            [
                sys.executable,
                str(SCRIPT_DIR / "batch_note_pipeline.py"),
                str(empty_batch),
                "--work-dir",
                str(root / "batch-work"),
                "--stages",
                "preflight",
            ]
        )
        assert_true(batch_result.returncode != 0, "Empty batch record should fail preflight")

        full_batch = root / "full-batch.json"
        full_work = root / "full-batch-work"
        full_batch.write_text(
            json.dumps(
                {
                    "papers": [
                        {
                            "paper_key": "full-smoke",
                            "content_list": str(content_list),
                            "assets_dir": str(assets),
                            "note_path": str(note),
                            "note_assets_dir": str(assets),
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        full_batch_result = run(
            [
                sys.executable,
                str(SCRIPT_DIR / "batch_note_pipeline.py"),
                str(full_batch),
                "--work-dir",
                str(full_work),
                "--stages",
                "preflight,parse_cache,evidence_manifest,draft,review,quality,domain,validate,cleanup_report",
                "--continue-on-error",
                "--final-report",
                str(root / "batch-final-report.md"),
            ]
        )
        assert_true(full_batch_result.returncode == 0, full_batch_result.stdout + full_batch_result.stderr)
        full_sidecar = json.loads((full_work / "sidecars" / "full-smoke.json").read_text(encoding="utf-8"))
        assert_true(
            full_sidecar["stages"]["parse_cache"]["status"] == "complete",
            "batch sidecar parse_cache stage missing",
        )
        assert_true(
            full_sidecar["stages"]["draft"]["status"] == "complete",
            "batch sidecar draft checkpoint missing",
        )
        assert_true(
            full_sidecar["stages"]["review"]["status"] == "skipped",
            "batch sidecar review checkpoint should be explicit when not automated",
        )
        assert_true(
            full_sidecar["stages"]["quality"]["status"] == "failed",
            "batch sidecar quality gate should record short-note failure",
        )
        assert_true(
            "quality_report_path" in full_sidecar["paths"],
            "batch sidecar should record quality report path",
        )
        assert_true(
            "domain_report_path" in full_sidecar["paths"],
            "batch sidecar should record domain report path",
        )
        assert_true(
            "domain" in full_sidecar and full_sidecar["stages"]["domain"]["status"] in {"complete", "failed"},
            "batch sidecar should record domain gate stage",
        )
        assert_true(
            full_sidecar["counts"]["image_link_count"] >= 1,
            "batch sidecar cleanup counts missing",
        )
        assert_true(
            full_sidecar["counts"]["appendix_items"] >= 1,
            "batch sidecar should count appendix evidence separately",
        )
        assert_true(
            full_sidecar["counts"]["supplementary_items"] >= 2,
            "batch sidecar should count appendix and post-reference evidence as supplementary",
        )
        final_report_text = (root / "batch-final-report.md").read_text(encoding="utf-8")
        assert_true(
            "| paper_key | final | quality | domain | validation | repair | cleanup | note/source pack | issue |"
            in final_report_text,
            "batch final report should include domain status column",
        )

        bad_note = root / "bad.md"
        bad_note.write_text(
            "# Bad\n\n## 附录：MinerU 图片资源完整性索引\n\n"
            "- ![missing](assets/missing.png)\n",
            encoding="utf-8",
        )
        bad_result = run([sys.executable, str(VALIDATE_NOTE), str(bad_note), "--json"])
        assert_true(bad_result.returncode != 0, "Bad note unexpectedly passed validation")

    print("smoke tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
