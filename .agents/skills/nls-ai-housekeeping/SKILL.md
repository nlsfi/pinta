---
name: nls-ai-housekeeping
description: Manual two-stage procedure for auditing and refreshing AI-agent instruction and repository documentation, keeping one clear source of truth, and handing Copier-managed updates back to a developer.
---

## A. When to use  <!-- markdownlint-disable-line MD041 -->

Use this skill only when a developer explicitly asks for AI instruction housekeeping.

- Manual invocation only.
- No autodetection, no scheduled runs, no background monitoring.
- Goal: keep instruction files accurate, lean, and non-duplicative.

### Source-of-truth rules

- Repository-wide policy, primary source: root `AGENTS.md`.
- Domain procedures: the relevant `SKILL.md`.
- Repository-specific facts and architecture: repository documentation.

## B. Copier template freshness gate (required)

This is a confirmation gate, not an independent Copier freshness check. Ask the developer to confirm that the relevant template source is up to date.

Because this skill file is itself generated from a Copier template, run this check before Stage 1:

1. Remind the developer to confirm whether Copier templates are up to date (or to run Copier update first).
2. Pause and wait for explicit developer response.
3. If developer confirms templates are up to date, continue to Stage 1.
4. If developer says templates need updating, stop here and instruct them to run Copier update, then invoke this skill again in a fresh context (because update may change this skill).

## C. Two-stage workflow (after B1 passes)

### Stage 1: Audit + plan (read-only)

Do not write files in this stage.
For Copier-managed files, do not edit generated consumer copies.

1. Inventory instruction surfaces and relevant repository documentation that exist. Include root and scoped `AGENTS.md`, `.agents/**/*.md`, `README.md` files, `component-map.md`, `domain-model.md`, and other Markdown files that describe architecture, components, domains, APIs, workflows, setup, or operational behaviour. Exclude generated consumer copies from edits and clearly label them as generated when reporting findings.
2. Compare content for duplication, contradiction, stale guidance, missing links, and mismatch with the current code, configuration, and directory structure.
3. For `component-map.md` (or an equivalent component document), trace each documented component to the current code, configuration, or deployable boundary. Check that important components, ownership or responsibility boundaries, dependencies, and integration points are represented accurately. Flag undocumented components only when documenting them would help an agent understand the system or avoid a likely mistake; do not require exhaustive inventories.
4. For `domain-model.md` (or an equivalent domain document), trace each documented domain term, entity, relationship, and boundary to the current code and repository vocabulary. Check that important terms are defined consistently, especially terms that are easy to confuse, overloaded, or used differently across modules. Flag important or risky undocumented terms, but do not require documentation of obvious implementation details.
5. For every reviewed README or other relevant Markdown document, ask: **Is the documentation in line with the code?** If not, identify the exact stale or misleading statement and suggest a concrete improvement. Check examples, commands, paths, module names, configuration names, and links against the repository.
6. Identify components and domain terms present in documentation but no longer present in the code, configuration, or current repository structure. Treat them as candidates for removal or archival, and distinguish confirmed obsolete items from items that need developer verification.
7. Build a concrete change plan per file, including additions, corrections, removals, and any facts that require developer confirmation.
8. Present the plan and ask for explicit approval before Stage 2.

### Stage 2: Apply approved updates

Only proceed after explicit developer confirmation.

1. Apply only approved changes.
2. Keep instructions lean; move process detail into skills instead of ambient instruction files.
3. Rebuild `AGENTS.md` module links from actual files present.
4. Re-check documentation claims against the current code and repository structure, including component boundaries and domain terminology.
5. Re-check for conflicts between source-of-truth files.
6. Produce a final housekeeping report (template in section E).

## D. File-by-file checklist

Review each surface when present:

- `AGENTS.md` (root and any scoped versions)
- `.agents/**/*.md` (Copier-managed)
- `component-map.md` and `domain-model.md` (if present, including equivalent or differently named documents)
- `README.md` files at the root and in relevant components
- Other relevant `*.md` files, including architecture, API, workflow, setup, operations, and glossary documentation
- Instruction-linked docs, links, indexes, and routing wiring

Checks to perform:

- Accuracy to current repository structure and tooling.
- Documentation is in line with the code, configuration, and actual commands; discrepancies have a specific suggested improvement.
- Important components and responsibility boundaries are documented where useful, without requiring an exhaustive component inventory.
- Important domain terms, entities, relationships, and boundaries are documented consistently, especially terms that could be confused or have multiple meanings.
- Components and domain terms documented but absent from current code or repository structure are flagged as candidates for removal or archival.
- Examples, paths, links, configuration names, and module names in Markdown are current and usable.
- No duplicated or conflicting policy across files.
- Procedures stay in skill files; primary instructions keep always-needed facts.
- Stale guidance and linter-enforced restatements removed or trimmed.
- `Known pitfalls` remains concrete and short.
- Weak skill descriptions that may fail trigger matching are flagged.

## E. Output report template

Use this format at the end of a housekeeping run:

```markdown
## AI Instruction Housekeeping Report

### Files changed
- <path>: <what changed and why>

### Verification checks

Mark completed checks with `[x]`; mark non-applicable checks as `[N/A]` and explain them under Residual risks.

- [ ] No conflicting duplicate policy between primary and secondary instruction files
- [ ] `AGENTS.md` links/routing match files that actually exist
- [ ] Component maps and domain models match the current code and use consistent terminology
- [ ] README and other relevant Markdown documentation matches the current code, commands, paths, and links
- [ ] Obsolete documented components and domain terms were removed, archived, or flagged as candidates for review
- [ ] Stale guidance removed or trimmed
- [ ] `Known pitfalls` is concrete and short

### Residual risks
- <any remaining uncertainty or deferred decisions>
```

## F. Guardrails

- Never fabricate completion; state what was and was not changed.
- Never apply edits in Stage 1.
- Always ask for confirmation before writing files.
- Keep one primary source of truth; keep secondary surface minimal or pointer-only.
- Keep instructions lean; avoid restating linter/tool-enforced rules unless truly necessary.
- If scope is unclear, stop and ask before editing.
- If Copier templates are not confirmed up to date, do not proceed past the freshness gate.
