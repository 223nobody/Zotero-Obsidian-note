# Source Order Rules

Use this file before drafting or upgrading `## 五、图片解释`, `## 六、表格与结论数据解释`, and `## 七、公式解释`.

## Goal

Keep the note's evidence explanations aligned with the original paper's reading order. The content and format of each explanation can stay the same; this rule is mainly about ordering.

## Build A Source-Order Inventory

Before drafting those three sections, create a private inventory from the paper or extracted Markdown:

| type | label | first location | caption / nearby heading | status |
| ---- | ----- | -------------- | ------------------------ | ------ |
| Figure | Figure 1 | page/section/line | <caption> | available / missing |
| Table | Table 1 | page/section/line | <caption> | available / missing |
| Equation | Equation 1 | page/section/line | <nearby method text> | available / missing |

Use the inventory to write the final note. Do not include this inventory in the final note unless the user asks for it.

## Ordering Rules

- In `## 五、图片解释`, order Figure entries by their first appearance in the original paper.
- In `## 六、表格与结论数据解释`, order Table entries by their first appearance in the original paper.
- In `## 七、公式解释`, order key Equation / Loss / Objective / Score / Constraint entries by their first appearance in the original paper.
- Keep the three section headings from `references/blueprint.md`; do not merge figures, tables, and formulas into one mixed evidence timeline unless the user explicitly asks.
- Preserve each item's explanation content and template structure when upgrading an existing note. Reorder first, then only edit content where evidence, terminology, or formatting actually needs repair.
- Do not sort by importance, narrative flow, innovation point, result strength, or how often the paper cites the item later.

## Ambiguous Cases

- If a figure/table/equation is referenced in text before it physically appears, order it by the caption/object's first appearance, not by the earlier prose reference.
- If extraction loses page or line locations, fall back to the paper's numbering order and mark `顺序依据：编号推断` in the internal self-check.
- If numbering is inconsistent, duplicated, or reset in appendices, preserve main-paper items first and put appendix/supplementary items after them unless the user asks for appendix-first coverage.
- If a table or equation is embedded inside a figure, explain it in the figure section unless the paper separately labels it as a table or equation.

## Final Check

Before delivery, quickly compare the final three sections against the inventory and verify that no item was moved to support a smoother narrative at the cost of original-paper order.
