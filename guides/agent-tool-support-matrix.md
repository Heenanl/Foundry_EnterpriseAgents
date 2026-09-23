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
| 1 | SharePoint grounding tool (`sharepoint_grounding_preview`) | Copilot Retrieval API | Yes | No — a deployed container has no user token(Read note below) | Yes | Yes | Site/folder | Copilot license or Retrieval API paygo | [SharePoint tool](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/sharepoint) | [Prompt sample](../foundryagents/promptagent/sharepoint-agent-grounding-tool/README.md) |
| 2 | Work IQ (`work_iq_preview`) | Work IQ over M365 | Yes | Yes | Yes | Yes | Broad M365, no per-site filter | Work IQ API paygo; connector licensing differs | [Work IQ](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/work-iq) | [Work IQ sample](../foundryagents/hostedagent/sharepoint-agent-workiq/README.md) |
| 3 | SharePoint retrieval: Toolbox + OBO MCP server | Copilot Retrieval API | MCP integration possible; Not in this repository | Yes | Yes | Yes | Site/path in sample | Copilot license or Retrieval API paygo | [Toolbox](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/use-toolbox-hosted-agent) · [MCP](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/model-context-protocol) · [Retrieval API](https://learn.microsoft.com/microsoft-365/copilot/extensibility/api/ai-services/retrieval/overview) | [SharePoint retrieval](../foundryagents/hostedagent/sharepoint-copilot-retrieval/README.md) |


**Note** : Why a deployed hosted agent can't use sharepoint_grounding_tool. The tool's grounding runs through OBO, which needs a user assertion to exchange. The docs' hosted-agent sample
supplies one via AzureCliCredential — it runs on your machine as you. Deploy that same code and the
credential becomes the container's own agent identity, so there is no user to act for and the call
fails with "AppOnly OBO tokens not supported." Options 2 and 3 survive deployment because the user
arrives through the connection's consent flow rather than the caller — Option 3 was built to overcome the limitations of sharepoint_grounding_tool and get site-scoped Retrieval API results into a deployed, Teams-published agent.


Publishing is the same for all four — the Foundry auto-bot via
[`scripts/Publish-AgentToTeams.ps1`](../scripts/Publish-AgentToTeams.ps1), prompt agents included.

A successful answer never proves trimming; verify the downstream caller identity yourself. These
samples configure a site `path` filter only; file-type or date filtering is an implementation change,
not a sample setting.

## Pros / cons

| Option | Pros | Constraints |
| --- | --- | --- |
| SharePoint grounding tool | Managed grounding with site/folder scope | Requires delegated context; not an app-only hosted-container route |
| Work IQ | Broad Microsoft 365 context without a custom retrieval gateway | No site-specific scope; review connection-specific licensing and consent |
| SharePoint retrieval (Toolbox + OBO MCP server) | Keeps the Foundry auto-bot; centralizes OBO in one server | Interactive tool OAuth consent and an extra service to operate |
| Model-only prompt agent | No retrieval infrastructure | Cannot provide permission-trimmed enterprise grounding |

## Recommendation

- For **hosted, site-scoped SharePoint retrieval**, use the Foundry auto-bot plus interactive tool consent. A retired shared-bot variant with silent Teams SSO is kept for reference in [deprecated/pathB](../deprecated/pathB/README.md).
- For broad Microsoft 365 grounding, consider Work IQ. For a prompt-only solution, consider the SharePoint grounding sample and confirm current Teams/channel support.
- Use **Foundry Agent Consumer** for invocation at the narrowest supported agent/project scope and **Foundry User** for the agent identity's model calls at project scope. Do not assume tenant publishing or `BotServiceRbac` removes caller authorization requirements.
- Retrieval API pay-as-you-go requires at least one Microsoft 365 Copilot license in the tenant. Work IQ billing and SharePoint-agent billing do not automatically entitle the raw Retrieval API.

## Customer validation

Complete the [two-user checklist](verify-per-user-isolation.md)
with a known document, a user who can read it, and a user who cannot. Compare authenticated tool
identities and raw retrieval outcomes in separate sessions; do not use a model answer or blocked
citation link as proof of permission trimming. Repeat for each connection and target network posture.
