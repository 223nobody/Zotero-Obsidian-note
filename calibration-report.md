# Step 1 校准报告：SkCC 样本笔记 9-Gate 验证

生成时间：2026-06-29

## 样本信息

- **论文**：SkCC: Portable and Secure Skill Compilation for Cross-Framework LLM Agents
- **论文类型**：System（四阶段编译流水线）
- **领域**：agent-skill
- **证据项**：24 项（23 required_in_final, 1 excluded）
- **样本笔记路径**：work/obsidian-notes/26-6-29/SkCC-Portable-and-Secure-Skill-Compilation.md

## 9-Gate 验证结果

| Gate | 工具 | 结果 | 详情 |
|------|------|------|------|
| 1. preflight | batch_note_pipeline.py | ✅ pass | 所有源文件路径存在 |
| 2. source pack | batch_note_pipeline.py | ✅ pass | source-pack.json 已生成 |
| 3. evidence manifest | build_evidence_manifest.py | ✅ pass | 24 items, 23 required_in_final (95%) |
| 4. blueprint structure | validate_note.py --blueprint | ✅ pass | 8 个 H2 章节符合 blueprint.md |
| 5. evidence coverage | validate_note.py --strict-evidence | ❌ fail | 11/23 required items 未在正文中显式引用 |
| 6. asset gate | validate_note.py | ✅ pass | 无 MinerU asset dump（assets 目录为空） |
| 7. quality gate | audit_note_quality.py | ❌ needs_major_repair | evidence_coverage=0.48, terminology=0.75 |
| 8. domain consistency | validate_domain_consistency.py | ⚠️ needs_minor_repair | 6/8 checks pass |
| 9. final delivery | batch_note_pipeline.py | ❌ fail | evidence coverage + quality 未通过 |

## 校准发现

### 1. `required_in_final` 阈值修正

**问题**：原逻辑将所有 `main` 区域的 medium+ confidence 项标记为 required → 97.3% items required
**修正**：新增 `core_level` 和 `label` 参数，只对 `core_candidate` + medium+ confidence 的主区域项标记 required → 降至 89%
**效果**：更精准地区分核心证据项和非核心项

### 2. `audit_note_quality.py` 中文章节检测修复

**问题**：`section_by_keywords` 在 H2 章节含 H3 子章节时，H2 body 为空（body 只包含到第一个子标题之间的文本）
**修正**：新增 `section_body_with_children()` 函数递归包含子章节内容；改用 `best` 匹配优先选择较浅层级的标题
**效果**：innovation_analysis 等评分从 0.03 → 1.00

### 3. `smoke_test_skill.py` 冲突标记误报修复

**问题**：`=======` 作为分隔注释（如 `# ========...`）被当作 git 冲突标记
**修正**：改用行首锚定正则 `^<<<<<<< ` 替代子串匹配
**效果**：消除 false positive

### 4. 样本笔记 evidence_coverage 分析

11/23 项未显式引用（Table 7-15, Figure 6, Score, Loss）的原因：
- 笔记将 Table 6-15 合并为一个段落描述（"本文有 15 个表格..."）
- 未逐项使用 `Table N` 标签

**建议**：对于论文中连续编号的同类表格，可以在保持合并解释的同时，添加显式编号列表（如 "Table 7-15 分别展示..."）

### 5. Quality audit 阈值初步校准

基于 SkCC 样本（一篇信息密度较高的 system 论文）：
- `pass` 阈值（scores 全部 ≥ 0.7）对此类论文可行
- `blueprint_structure` 的 6 个 H2 阈值合适
- `terminology` 评分（仅检查 `English（中文）` 模式）过于简化，建议后续增加对高频术语的检测
- `evidence_coverage` 评分（从 manifest 计算）客观且有用

### 6. Domain consistency 验证

- 正确检测到 "agent-skill" 领域（92% 置信度）
- 正确检测到 "system" 论文类型（62% 置信度）
- 6/8 checks pass
- 2 个 minor failure 准确识别了 innovation_scoped regex 匹配问题和 boundary_conditions 项数不足

## 后续改进建议

### P0: 补全 11 篇样本笔记
当前只有 SkCC 一篇样本完成验证。需要对其他 10 篇执行相同的流程以获得统计显著的校准数据。

### P1: 细化 quality audit 阈值
- 对 survey 论文：method_explanation 和 innovation_analysis 可能天然偏低（综述不提出新方法）
- 对 benchmark 论文：evidence_depth 应重点检查 dataset 和 metric 的覆盖
- 建议按论文类型使用不同的权重向量

### P1: 改进 `innovation_scoped` 的 regex
validate_domain_consistency.py 中的 innovation 章节匹配 regex 过于严格，无法匹配包含标点符号的中文标题。

### P2: 解决 MinerU assets 为空的问题
当前所有 11 篇论文的 MinerU `assets/` 目录为空（0 文件），导致 `asset_match_status` 全部为 "missing"。这可能是因为 `paper-search-mcp` 解析时选用了 `pypdf` 后端而不是 `mineru` 后端。

## 最终结论

三轮校准（`required_in_final` 修正、`audit_note_quality.py` 章节检测修复、`smoke_test_skill.py` 误报修复）完成后，三套 gate 脚本均能对样本笔记产生合理的判定结果。SkCC 样本笔记在 evidence_coverage 上需要改进（显式引用所有 required 证据项），这是预期中的校准反馈。skill 基础架构已准备好进行 11 篇全量试跑。
