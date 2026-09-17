# SharePoint / enterprise-data grounding options for Foundry agents

How each grounding option behaves across prompt and hosted agents.
Legend: ✅ supported, ❌ not supported, ⚠️ partial, 🧪 preview.

| # | Tool / route | Backed by | Prompt | Hosted | Teams | Per-user (trimmed) | Scoping | Licensing | Repo sample |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | SharePoint grounding tool (`sharepoint_grounding_preview`) 🧪 | Copilot Retrieval API | ✅ | ❌ (app-only) | ✅ as prompt, ❌ hosted | ✅ | one site/folder | Copilot license or Retrieval API paygo | `promptagent/sharepoint-agent-grounding-tool` |
| 2 | Work IQ (`work_iq_preview`) 🧪 | Work IQ over M365 | ✅ | ✅ | ✅ | ✅ | none (broad M365) | Copilot license or Work IQ paygo | `hostedagent/sharepoint-agent-workiq` |
| 3 | Databricks Genie (remote MCP) 🧪 | Databricks Genie | ✅ | ✅ | ✅ | ⚠️ shared token, not per-user | Genie space | Databricks | `hostedagent/databricks-agent` |
| 4 | MCP-OBO gateway (Retrieval API) 🧪 | Copilot Retrieval API | ✅ | ✅ | ✅ | ⚠️ shared token in testing (Path A) | site / path / file type / date | Copilot license or Retrieval API paygo | `hostedagent/sharepoint-copilot-retrieval/pathA` |
| 5 | Basic prompt agent (model only) | model deployment | ✅ | n/a | via publish | n/a | n/a | model only | `promptagent` |
| 6 | Shared bot + `x-client-user-token` (in-code OBO) | Copilot Retrieval API | n/a | ✅ | ✅ | ✅ **verified** | site / path / file type / date | Copilot license or Retrieval API paygo | `hostedagent/sharepoint-copilot-retrieval/pathB` |

## What decides the outcome

Identity: a prompt agent runs as the signed-in user (OBO); a hosted container runs as its own managed
identity (app-only). A hosted agent is *intended* to get per-user access when Foundry brokers the
user's token through an OAuth2 identity-passthrough connection (rows 2, 3, 4) — but in our testing the
MCP-OBO gateway (row 4, **Path A**) returned the **first-consented (admin) token**, not per-user, so
treat it as shared until verified for your tenant. The verified per-user route today is row 6
(**Path B**), where a shared bot forwards each user's own Teams-SSO token on `x-client-user-token` and
the agent does the OBO in code. This is also why the native SharePoint grounding tool works in a
prompt agent but is rejected app-only in a hosted one.

Scoping: only the SharePoint grounding tool (site/folder) and the Retrieval API filter expression
(site, path, file type, date) scope to a single site. Work IQ reasons over broad M365 and does not
scope per site.

## For hosted + Teams

Work IQ, Databricks Genie, and the MCP-OBO gateway all run from a hosted agent on the Foundry auto-bot,
because they use OAuth2 identity-passthrough where Foundry brokers the token. The MCP-OBO gateway
applies that to the Copilot Retrieval API with site scoping — but **in testing it returned a shared
(first-consented) token, not per-user** (Path A). For **verified per-user** trimming today, use the
shared bot + `x-client-user-token` in-code OBO route (Path B). See the
[decision matrix](per-user-sharepoint-obo-teams-decision-matrix.md) and
[../foundryagents/hostedagent/sharepoint-copilot-retrieval/pathA/obo-gateway/README.md](../foundryagents/hostedagent/sharepoint-copilot-retrieval/pathA/obo-gateway/README.md).
