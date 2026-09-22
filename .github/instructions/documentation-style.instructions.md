---
description: Documentation house style for this repo — keep all README and guide markdown consistent.
applyTo: "**/*.md"
---

# Documentation style guide

Apply these conventions to every `README.md` and `guides/*.md` in this repo so docs stay consistent
and customer-shareable. Match the existing samples (e.g. `hostedagent/databricks-agent/README.md`,
`hostedagent/sharepoint-copilot-retrieval/README.md`).

## Structure — per-sample README

Use this section order (omit sections that don't apply; never invent new top-level shapes):

1. `# <Title>` — one H1 only, the sample name/purpose.
2. **Intro paragraph** — 2–4 sentences: what it demonstrates, the protocol/framework, and the
   headline behavior (e.g. "per-user, permission-trimmed … published to Teams").
3. `## How it works` (or `## Why this exists`) — the mechanism, with a **Mermaid** diagram
   (` ```mermaid ` + `flowchart LR`). Link the key source file inline.
4. `## Prerequisites` — a **numbered** list. End with a `Placeholders used below:` line listing every
   `<ANGLE_CAPS>` token used in commands.
5. `## Deploy` (or `## Option 1: Azure Developer CLI (azd)` / `## Option 2: VS Code`) — copy-paste
   PowerShell blocks.
6. `## Publish to Teams` — when relevant.
7. `## Troubleshooting` — a **table**: `| Symptom | Cause / fix |`.
8. `## Next steps` — bullet links to related docs.

## Structure — decision guides (`guides/`)

Problem statement → the options (each with a short architecture + Mermaid) → a **decision matrix
table** → **Pros / cons** per option → **Recommendation** → verification steps. Keep any
product-group/roadmap notes in a dated section.

## Formatting rules

- **Headings:** exactly one `#` (title); all sections are `##`; sub-sections `###`. Never use `#`
  for a mid-document section.
- **Emphasis:** bold key terms and decisions (`**per-user**`, `**not** supported`). Use backticks
  for identifiers, env vars, file paths, roles, and commands (`` `x-client-user-token` ``,
  `` `Foundry Agent Consumer` ``).
- **Diagrams:** architecture/flows use ` ```mermaid ` `flowchart LR` (or `sequenceDiagram`), not ASCII.
- **Tables** for matrices, role assignments, env vars, and troubleshooting.
- **Links:** relative markdown links to repo files/folders (`[main.py](path/main.py)`); real doc
  URLs for Microsoft Learn. Never fabricate links.
- **Placeholders:** `<SUBSCRIPTION_ID>`, `<RESOURCE_GROUP>`, `<FOUNDRY_ACCOUNT>`, `<PROJECT>`,
  `<APP_ID>`, `<obo-app-id>`, etc. Never commit real secrets, tenant-specific ids, or tokens.
- **Commands:** PowerShell in ` ```powershell ` blocks; one action per block; comment non-obvious lines.

## Accuracy rules

- Docs must match the **deployed reality** — when code/config changes (agent name, env var, role,
  header), update every README that references it in the same change.
- Distinguish **verified** from **preview/unverified**: state what was tested and how (e.g. "verified:
  admin gets the doc, testuser gets nothing"). Call out preview features and known gaps.
- Prefer **least-privilege** guidance (scope roles to the agent/project, not the account) and name the
  exact built-in role. For this repo: **Foundry Agent Consumer** (call agents), **Foundry User** (call
  models); do **not** recommend `Cognitive Services *` or `Azure AI Developer` for Foundry agents.
- No marketing tone. Be concise and factual; a customer should be able to act from the doc.
