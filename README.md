# Zotero-Obsidian-Note

`zotero-group-meeting-note` 是一个面向 Codex 的中文研究生组会文献汇报 skill。它用于从 Zotero 当前论文、PDF、已有 Zotero 笔记或论文解析后的 Markdown 中生成可直接用于组会分享的深度笔记，并可保存到 Zotero 兼容 Markdown 与 Obsidian。

本 skill 的重点不是复述论文，而是帮助汇报者讲清：论文的创新点是什么，证据链是否充分，图片、表格、公式和结论数据如何解释，以及它与相关工作的对比和联系在哪里。

#### 当前 skill 是对 Zotero+Obsidian 论文工作流的尝试，欢迎随意修改进行自定义实现更多玩法。亲测分析一篇论文约消耗 codex gpt5.4 high 周额度的 5%。

## 直接生成论文 prompt 提示词

### ！！！一定要在提示词前先使用'/'调用插件原生的 write-note 的 skill，效果更好

```text
请你阅读当前 md 格式论文，调用 "~\.codex\skills\.system" 下的 zotero-group-meeting-note skill，基于当前论文生成一份详细的组会分享笔记，并同时保存到 Zotero 和 Obsidian。
```

## 默认输出效果

如果用户没有指定输出位置，默认写入：

```text
~/Documents/Obsidian Vault/组会分享/<yy-M-d>/<论文标题>.md
```

示例：

```text
~/Documents/Obsidian Vault/组会分享/26-4-20/Adversity-aware Few-shot Named Entity Recognition via Augmentation Learning.md
```

同时在同级目录创建：

```text
assets/
```

默认规则：

- 文件名默认使用可读论文标题，不使用小写 slug。
- 文件名默认不添加 `group-meeting`、日期后缀或 `组会分享笔记：` 前缀。
- 正文 H1 默认使用 `# 组会分享笔记：<论文标题>`。
- 默认不写 YAML frontmatter。
- 默认不写 `Written by LLM-for-Zotero` 等插件签名。

## 核心能力

- 创新点分析：说明相对旧方法的变化、意义、证据和边界。
- 图片解释：解释方法图、架构图、曲线图、可视化图、案例图与数据分布图。
- 表格与结论数据解释：分析主实验、强基线、消融、鲁棒性、泛化、效率和人评结果。
- 公式解释：把目标函数、打分公式、表示学习公式、推断公式、复杂度公式转成组会讲法。
- 原文顺序：图片、表格、公式三节分别按论文中首次出现顺序排列。
- 术语润色：对高频专业英文短语做首次中英对照，并保持译名一致。
- 交付复核：生成后检查证据覆盖、待核对项、术语一致性和口语化表达。
- 相关工作定位：说明论文继承、改进、组合或区别于哪些路线。
- 输出落盘：通过 `scripts/prepare_output.py` 确定文件名、日期目录、assets 目录和自定义路径。

## 推荐调用方式

### 1. 默认生成到 Obsidian Vault

```text
$zotero-group-meeting-note
请基于当前 Zotero 论文生成一份组会分享笔记，重点解释创新点、关键图片、表格、公式、结论数据和相关工作对比。
```

默认输出到：

```text
~/Documents/Obsidian Vault/组会分享/<yy-M-d>/<论文标题>.md
```

### 2. 指定日期文件夹

```text
$zotero-group-meeting-note
请基于当前 Zotero 论文生成组会分享笔记，日期文件夹使用 26-4-20。
```

目标效果：

```text
~/Documents/Obsidian Vault/组会分享/26-4-20/<论文标题>.md
```

### 3. 指定完整输出文件名

```text
$zotero-group-meeting-note
请输出到 ~/Documents/Obsidian Vault/组会分享/26-4-20/Adversity-aware Few-shot Named Entity Recognition via Augmentation Learning.md。
```

当用户给出完整 `.md` 路径时，以该路径为最高优先级。

### 4. 指定 Obsidian 仓库根目录

```text
$zotero-group-meeting-note
请将笔记保存到 D:\Obsidian\ResearchVault，目录结构仍为 组会分享\<日期>\<论文标题>.md。
```

目标效果：

```text
D:\Obsidian\ResearchVault\组会分享\<yy-M-d>\<论文标题>.md
```

### 5. 指定精确输出文件夹和文件名

```text
$zotero-group-meeting-note
请将笔记保存到 D:\Notes\Seminar\26-4-20，文件名为 Adversity-aware Few-shot Named Entity Recognition via Augmentation Learning.md。
```

### 6. 自定义正文标题

```text
$zotero-group-meeting-note
请保存到默认 Obsidian 位置，但正文标题使用：# Few-shot NER 组会分享。
```

### 7. 只输出 Obsidian，不保留当前文件夹副本

```text
$zotero-group-meeting-note
请只生成 Obsidian 笔记，不在当前文件夹保留 Zotero 兼容 Markdown 副本。
```

### 8. 只生成 Zotero 兼容 Markdown

```text
$zotero-group-meeting-note
请只生成 Zotero 兼容 Markdown，不创建 Obsidian 文件。
```

### 9. 强化已有笔记

```text
$zotero-group-meeting-note
请基于当前 Zotero 笔记继续完善，不要重写已有结构。重点补充创新点分析、Table 1-3 的实验解释、与相关工作的对比，以及 5-8 分钟汇报提纲。
```

### 10. 只要 PPT 提纲

```text
$zotero-group-meeting-note
请把这篇论文整理成 8 分钟组会 PPT 提纲，每页给标题、要点、建议放哪张图表和口头讲法。
```

## 脚本工具

`scripts/prepare_output.py` 用于确定性处理文件名、目录和 assets。它不会生成正文，只做机械文件工作。
`scripts/extract_terms.py` 用于从论文 Markdown 或 text 中抽取高频英文缩写和多词术语候选，辅助生成 `English phrase（中文翻译）` 形式的术语对照。

默认用法：

```powershell
python scripts/prepare_output.py --article-filename "Adversity-aware Few-shot Named Entity Recognition via Augmentation Learning.pdf" --date "2026-04-20" --create-note-stubs
```

输出路径类似：

```text
~/Documents/Obsidian Vault/组会分享/26-4-20/Adversity-aware Few-shot Named Entity Recognition via Augmentation Learning.md
```

指定完整输出文件夹和文件名：

```powershell
python scripts/prepare_output.py `
  --article-filename "Adversity-aware Few-shot Named Entity Recognition via Augmentation Learning.pdf" `
  --obsidian-dir "$env:USERPROFILE\Documents\Obsidian Vault\组会分享\26-4-20" `
  --note-filename "Adversity-aware Few-shot Named Entity Recognition via Augmentation Learning.md" `
  --create-note-stubs
```

复制图片或解析产物到 `assets/`：

```powershell
python scripts/prepare_output.py `
  --article-filename "Example Paper.pdf" `
  --asset ".\figure1.png" `
  --asset-dir ".\paper-assets"
```

常用参数：

| 参数                  | 作用                                            |
| --------------------- | ----------------------------------------------- |
| `--article-filename`  | 论文标题或 PDF 文件名，用于推导默认文件名       |
| `--note-filename`     | 自定义 Markdown 文件名                          |
| `--note-title`        | 自定义正文 H1 标题                              |
| `--date`              | 自定义日期文件夹，支持 `YYYY-MM-DD` 或 `yy-M-d` |
| `--obsidian-vault`    | 自定义 Obsidian 仓库根目录                      |
| `--obsidian-dir`      | 自定义精确输出文件夹                            |
| `--asset`             | 复制单个图片/资产文件，可重复                   |
| `--asset-dir`         | 复制目录下的直接文件                            |
| `--create-note-stubs` | 创建只含标题的 Markdown 占位文件                |
| `--no-obsidian`       | 不创建 Obsidian 文件                            |
| `--no-zotero-file`    | 不创建当前文件夹 Zotero 兼容 Markdown           |

术语候选抽取：

```powershell
python scripts/extract_terms.py ".\paper.md" --top 30
```

## 领域模板

`references/` 下提供多个可按需加载的领域模板：

- `domain-llm.md`：LLM、RAG、Agent、工具调用、推理、对齐、评测。
- `domain-nlp.md`：分类、NER、信息抽取、问答、生成、翻译、多语言、低资源 NLP。
- `domain-cv.md`：分类、检测、分割、生成、扩散、多模态视觉、视觉语言模型。
- `domain-ml.md`：通用机器学习、表示学习、优化、鲁棒性、不确定性、AutoML、联邦学习。
- `domain-rl.md`：在线/离线强化学习、模仿学习、多智能体、安全 RL、多目标 RL、机器人控制。
- `domain-kg.md`：知识图谱构建、补全、推理、实体对齐、KGQA、知识增强生成。

领域模板只提供“应该关注什么”的检查角度。最终笔记仍以论文原文、图表、公式和实验数据为准。

## 仓库结构

```text
├── README.md
└── zotero-group-meeting-note/
    ├── SKILL.md
    ├── agents/
    │   └── openai.yaml
    ├── references/
    │   ├── blueprint.md
    │   ├── domain-cv.md
    │   ├── domain-kg.md
    │   ├── domain-llm.md
    │   ├── domain-ml.md
    │   ├── domain-nlp.md
    │   ├── domain-rl.md
    │   ├── output.md
    │   ├── review-pass.md
    │   ├── source-order.md
    │   └── terminology.md
    └── scripts/
        ├── extract_terms.py
        └── prepare_output.py
```

## 输出质量标准

最终笔记应该满足：

- 保存路径符合 `Obsidian Vault\组会分享\<日期>\<论文标题>.md` 或用户自定义路径。
- 一开头就能讲清论文核心结论和创新点。
- 每个创新点都有对应证据和边界。
- 关键图片、表格、公式都有自然语言解释和组会讲法。
- 图片、表格、公式三节内部按原论文首次出现顺序排列。
- 高频专业英文短语在首次关键出现处给出中文翻译。
- 实验数据分析能指出强基线、关键提升、异常点和证据缺口。
- 相关工作对比能说明论文继承了什么、改进了什么、没有比较什么。
- 局限与讨论问题具体到方法、数据、训练、评测或应用场景。
