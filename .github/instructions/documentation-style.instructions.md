---
description: Documentation house style for this repo — keep all README and guide markdown consistent.
applyTo: "**/*.md"
---

# Documentation style guide

Docs are for customers who want to replicate a sample. Keep them **crisp, concise, and easy to
follow**. Match the existing samples, for example
`foundryagents/hostedagent/sharepoint-knowledge-base/README.md`.

## Sample README structure

Use this order and omit sections that don't apply:

1. `# <Title>` — one H1.
2. **Intro** — 1–2 sentences: what the sample does and the headline behavior.
3. `## How it works` — a short **Mermaid** `flowchart LR` and a few sentences. Link the key source file.
4. `## Prerequisites` — short bullets.
5. `## Deploy` — numbered steps with copy-paste PowerShell blocks.
6. `## Publish to Teams` — when relevant.
7. `## Verify` — short, when relevant.
8. `## Learn more` — a few links.

Do **not** add troubleshooting sections, symptom tables, or lists of past failures.

## Formatting

- One `#` heading; sections are `##`, sub-sections `###`.
- Bold key terms sparingly. Use backticks for identifiers, env vars, paths, roles, and commands.
- Relative links for repo files; real Microsoft Learn URLs. Never fabricate links.
- Placeholders in `<ANGLE_CAPS>`. Never commit secrets, tenant IDs, or real site URLs.
- PowerShell in ` ```powershell ` blocks.

## Accuracy

- Docs must match the deployed code and config. Update every README a change affects.
- Name exact least-privilege roles: **Foundry Agent Consumer** to call agents, **Foundry User** for
  model access. Don't recommend `Cognitive Services *` or `Azure AI Developer` roles.
- No marketing tone.
