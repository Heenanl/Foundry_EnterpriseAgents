# SharePoint grounding tool (prompt agent)

A prompt agent that grounds answers in a SharePoint site with the Foundry **SharePoint tool**
(`sharepoint_grounding_preview`). It runs **as the signed-in user**, so answers are trimmed to that
user's permissions.

## Where it works

The SharePoint tool needs the user's delegated identity:

| Runs under | Supported |
| --- | --- |
| Signed-in user (this sample, or the playground) | Yes |
| Prompt agent published to Teams | Yes (verified in testing) |
| Hosted agent container (app-only identity) | No |

For hosted agents, use the [SharePoint knowledge base](../../hostedagent/sharepoint-knowledge-base/README.md)
sample.

## Prerequisites

- A **Microsoft 365 Copilot** licence for the user, or
  [Retrieval API pay-as-you-go](https://learn.microsoft.com/microsoft-365/copilot/extensibility/api/ai-services/retrieval/paygo-retrieval)
  enabled in the tenant.
- SharePoint site and Foundry project in the **same Entra tenant**.
- **Foundry User** on the project, and read access to the site.
- Python 3.10+.

## Deploy

1. In the Foundry portal, open your project and go to **Connections** > **New connection** >
   **SharePoint**. Enter the site URL, for example `https://<TENANT>.sharepoint.com/sites/<SITE>`.

2. Configure and run [sharepoint_agent.py](sharepoint_agent.py) as the user:

   ```powershell
   python -m venv .venv; .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   Copy-Item .env.example .env   # set SHAREPOINT_CONNECTION_NAME and the project values
   az login
   python sharepoint_agent.py
   ```

   You should get an answer with citations to the source documents.

## Verify

Pick a document that one user can read and another cannot. Ask the same question after `az login` as
each user. Only the user with access should get the content and citation.

## Learn more

- [Use the SharePoint tool](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/sharepoint)
- [Copilot Retrieval API](https://learn.microsoft.com/microsoft-365/copilot/extensibility/api/ai-services/retrieval/overview)
