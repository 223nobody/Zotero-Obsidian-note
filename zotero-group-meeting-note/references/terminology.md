# Terminology Reference

Use this file during the terminology pass in `references/review-pass.md`. Prefer these renderings when they fit the paper context, but keep author-defined names and official dataset/model/benchmark names searchable.

## Workflow

1. If paper text is available, run `scripts/extract_terms.py <source-file>` to get recurring English term candidates.
2. Pick terms that are central to the paper or appear repeatedly.
3. Translate the first important mention as `English phrase（中文翻译）`.
4. Keep the same Chinese rendering throughout the note.
5. Keep acronyms when they are the paper's main surface form, for example `MORL（多目标强化学习）`.

## General ML / Optimization

| English | Chinese |
| ------- | ------- |
| objective function | 目标函数 |
| loss function | 损失函数 |
| optimization objective | 优化目标 |
| constraint | 约束 |
| regularization | 正则化 |
| representation learning | 表示学习 |
| feature extraction | 特征提取 |
| latent space | 潜在空间 |
| embedding space | 嵌入空间 |
| decision boundary | 决策边界 |
| Pareto optimal policies | 帕累托最优策略 |
| Pareto Frontier | 帕累托前沿 |
| multi-objective reinforcement learning | 多目标强化学习 |
| off-policy learning | 离策略学习 |
| policy gradient | 策略梯度 |
| reward function | 奖励函数 |

## LLM / Agent / RAG

| English | Chinese |
| ------- | ------- |
| large language model | 大语言模型 |
| retrieval-augmented generation | 检索增强生成 |
| tool use | 工具使用 |
| tool calling | 工具调用 |
| agent framework | 智能体框架 |
| planning module | 规划模块 |
| memory module | 记忆模块 |
| verifier | 验证器 |
| reranker | 重排序器 |
| preference optimization | 偏好优化 |
| alignment | 对齐 |
| instruction tuning | 指令微调 |
| supervised fine-tuning | 监督微调 |
| reinforcement learning from human feedback | 基于人类反馈的强化学习 |
| chain-of-thought | 思维链 |
| self-consistency | 自洽性 |
| faithfulness | 忠实性 |
| factuality | 事实性 |

## NLP

| English | Chinese |
| ------- | ------- |
| named entity recognition | 命名实体识别 |
| information extraction | 信息抽取 |
| relation extraction | 关系抽取 |
| sequence labeling | 序列标注 |
| span classification | 片段分类 |
| low-resource learning | 低资源学习 |
| few-shot learning | 小样本学习 |
| zero-shot learning | 零样本学习 |
| cross-domain transfer | 跨领域迁移 |
| distant supervision | 远程监督 |
| noisy labels | 噪声标签 |
| constrained decoding | 约束解码 |

## Computer Vision

| English | Chinese |
| ------- | ------- |
| object detection | 目标检测 |
| semantic segmentation | 语义分割 |
| instance segmentation | 实例分割 |
| self-supervised learning | 自监督学习 |
| weakly supervised learning | 弱监督学习 |
| data augmentation | 数据增强 |
| feature fusion | 特征融合 |
| multi-scale fusion | 多尺度融合 |
| attention map | 注意力图 |
| diffusion model | 扩散模型 |
| open-vocabulary | 开放词表 |
| domain adaptation | 领域自适应 |

## Good Inline Patterns

- 现实控制任务经常不止一个目标。多个目标之间通常冲突，所以不存在一个在所有目标上都最优的单一策略，而是需要学习一组覆盖不同偏好的 `Pareto optimal policies（帕累托最优策略）`。
- MORL 的目标就是近似 `Pareto Frontier（帕累托前沿）`，并能根据偏好向量输出合适策略。
- 这类方法的关键风险是 `off-policy learning（离策略学习）` 带来的分布偏移，因为训练数据和当前策略访问的状态可能不一致。
- 在 RAG 系统里，`retrieval-augmented generation（检索增强生成）` 的收益不只来自更长上下文，也来自检索结果对生成过程的约束。
- 对检测任务来说，`multi-scale fusion（多尺度融合）` 主要解决不同大小目标在同一特征层上难以同时表达的问题。

## What Not To Translate Aggressively

- Dataset names, benchmark names, model names, APIs, library names, venues, author names, citation keys, and variable symbols.
- Module names that the paper treats as brand-like identifiers.
- Generic terms that do not affect technical understanding in context.
