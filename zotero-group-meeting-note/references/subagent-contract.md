# Subagent Contract

Use this file when a batch run delegates work to subagents.

## Isolation

One subagent may process exactly one independent paper work unit.

Allowed inputs:

- the target paper's source pack
- the target paper's evidence manifest
- the target paper's copy map
- the target paper's current note
- the target paper's gate reports
- this skill's `SKILL.md` and required references

Forbidden inputs:

- another paper's final note body
- another paper's repair context
- another paper's evidence manifest
- shared prose from another paper

## Prompt Pack

The prompt pack for a subagent must include:

- `paper_key`
- exact note path and assets path
- source pack path
- evidence manifest path
- copy map path
- gate report paths
- current repair scope
- maximum repair round

It must not include cross-paper body text.

## Completion

The subagent may report a paper complete only after the paper independently passes validation, quality, domain, asset, unmatched-asset, and final-delivery gates. Otherwise it must return an unresolved item-level report.
