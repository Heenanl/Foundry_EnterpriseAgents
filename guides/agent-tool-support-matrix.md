# SharePoint / enterprise-data grounding options for Foundry agents

Choose a grounding route based on **user identity**, **site scoping**, and the agent hosting model.
A container's managed identity does not grant delegated SharePoint access. Any of these agents can be
published to Teams; what differs is whether the grounding tool still retrieves **as the signed-in
user** once it is. Preview tool availability and licensing must be checked for the chosen service and
deployment configuration.

## Decision matrix

The matrix describes route capabilities and constraints, not production certification. The native
SharePoint, Work IQ, and MCP integrations include preview features.

| # | Tool / route | Backed by | Prompt Agent | Hosted Agent | Teams Publishing | Per-user (trimmed) | Scoping | Licensing | Docs | Repo sample |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | SharePoint grounding tool (`sharepoint_grounding_preview`) | Copilot Retrieval API | Yes | No — a deployed container has no user token (see note) | No — the tool doesn't work in Teams ([documented limitation](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/sharepoint)) | Yes | Site/folder | Copilot license or Retrieval API paygo | [SharePoint tool](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/sharepoint) | [Prompt sample](../foundryagents/promptagent/sharepoint-agent-grounding-tool/README.md) |
| 2 | Work IQ (`work_iq_preview`) | Work IQ over M365 | Yes | Yes | Yes | Yes | Broad M365, no per-site filter | Work IQ API paygo; connector licensing differs | [Work IQ](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/work-iq) | [Work IQ sample](../foundryagents/hostedagent/sharepoint-agent-workiq/README.md) |
| 3 | SharePoint retrieval: Toolbox + OBO MCP server (**custom setup, superseded by option 4**) | Copilot Retrieval API | MCP integration possible; Not in this repository | Yes | Yes | Yes | Site/path in sample | Copilot license or Retrieval API paygo | [Toolbox](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/use-toolbox-hosted-agent) · [MCP](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/model-context-protocol) · [Retrieval API](https://learn.microsoft.com/microsoft-365/copilot/extensibility/api/ai-services/retrieval/overview) | [SharePoint retrieval](../foundryagents/hostedagent/sharepoint-copilot-retrieval/README.md) |
| 4 | SharePoint knowledge base: Toolbox + Foundry IQ remote SharePoint knowledge source (**recommended**) | Azure AI Search knowledge base over the Copilot Retrieval API | Supported through Foundry IQ; Not in this repository | Yes | Yes | Yes | Site/path filter on the knowledge source | Copilot license per user, plus Azure AI Search | [Remote SharePoint knowledge source](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-sharepoint-remote) · [Foundry IQ](https://learn.microsoft.com/azure/foundry/agents/how-to/foundry-iq-connect) · [Toolbox auth](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/tool-authentication) | [SharePoint knowledge base](../foundryagents/hostedagent/sharepoint-knowledge-base/README.md) |


**Note:** the SharePoint grounding tool needs a user token to exchange. Run locally, it uses your
`az login` identity. Deployed, the container has only its own agent identity, so the call fails with
"AppOnly OBO tokens not supported". Options 2–4 work when deployed because the user's identity
arrives through the connection instead.

**Option 3 vs option 4.** Option 3 is a **custom setup**: you build, host and operate your own OBO MCP
server. Option 4 supersedes it with built-in Foundry IQ components and is the route recommended by
the Microsoft Foundry product team. It is in preview with general availability expected; prefer it
for new work.

Options 2–4 publish to Teams the same way, through
[Publish-AgentToTeams.ps1](../scripts/Publish-AgentToTeams.ps1).

## Pros / cons

| Option | Pros | Constraints |
| --- | --- | --- |
| SharePoint grounding tool | Managed grounding with site/folder scope | Requires delegated context; not an app-only hosted-container route |
| Work IQ | Broad Microsoft 365 context without a custom retrieval gateway | No site-specific scope; review connection-specific licensing and consent |
| SharePoint retrieval (Toolbox + OBO MCP server) | Keeps the Foundry-managed bot; centralizes OBO in one server | Custom setup, superseded by option 4; interactive tool OAuth consent and an extra service to operate |
| SharePoint knowledge base (Toolbox + Foundry IQ) | Recommended route; no server to operate; site/path scoping on the knowledge source; no per-tool consent | Every user needs **Search Index Data Reader** on the Search service and a Copilot license; preview |
| Model-only prompt agent | No retrieval infrastructure | Cannot provide permission-trimmed enterprise grounding |

## Recommendation

- For **hosted, site-scoped SharePoint retrieval**, use the **Foundry IQ knowledge base route (option 4)**, the route recommended by the Microsoft Foundry product team. It needs every user to have a Search data-plane role and a Copilot license.
- Use the custom OBO MCP server (option 3) only where option 4 can't yet cover the requirement. A retired shared-bot variant with silent Teams SSO is kept for reference in [deprecated/pathB](../deprecated/pathB/README.md).
- For broad Microsoft 365 grounding, consider Work IQ. For a prompt-only solution, consider the SharePoint grounding sample and confirm current Teams/channel support.
- Use **Foundry Agent Consumer** for invocation at the narrowest supported agent/project scope and **Foundry User** for the agent identity's model calls at project scope. Do not assume tenant publishing or `BotServiceRbac` removes caller authorization requirements.
- Retrieval API pay-as-you-go requires at least one Microsoft 365 Copilot license in the tenant. Work IQ billing and SharePoint-agent billing do not automatically entitle the raw Retrieval API.

## Verify

Run the [two-user checklist](verify-per-user-isolation.md) for the route you choose. A successful
answer alone does not prove permission trimming.
