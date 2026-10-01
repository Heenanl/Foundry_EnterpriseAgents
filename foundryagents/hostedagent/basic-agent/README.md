# Basic agent — deploy, then publish to Teams

A minimal **Agent Framework** hosted agent with no tools and no connections. Deploy it, publish it to
Microsoft Teams, and confirm the end-to-end path works before you add a retrieval sample on top.

This is the agent used to verify the [native Microsoft 365 publishing route](../../../README.md).

## How it works

```mermaid
flowchart LR
  T[Teams or Microsoft 365] --> B[Azure Bot Service]
  B -->|Activity Protocol| A[contoso-support-agent]
  A -->|Responses| M[Model deployment]
```

[main.py](src/contoso-support-agent/main.py) builds one `Agent` over a `FoundryChatClient` and serves
it with `ResponsesHostServer`. [azure.yaml](azure.yaml) declares the model deployment and the
container.

## Prerequisites

1. A Foundry project, and a **`gpt-4.1`** model deployment (or edit the deployment in
   [azure.yaml](azure.yaml)).
2. **Azure CLI** and **Azure Developer CLI** 1.27.1+ with the Foundry extension:
   `azd ext install microsoft.foundry`.
3. **Roles (RBAC):** **Foundry User** on the project to deploy the agent, and **Foundry User** for
   the agent identity's model calls. People who only *chat* with the agent need
   **Foundry Agent Consumer** — not Foundry User.
4. **Python 3.12+** only if you want to run the agent locally.

Placeholders used below: `<FOUNDRY_ACCOUNT>`, `<PROJECT>`, `<PROJECT_ARM_ID>`, `<RESOURCE_GROUP>`.

## Deploy

From this folder:

```powershell
az login
```

```powershell
azd up
```

By default this **creates a new resource group, Foundry account, and project**, deploys the model, and
registers the agent version.

To deploy into an **existing** project, scaffold against its ARM resource ID. Setting
`AZURE_AI_PROJECT_ENDPOINT` alone does **not** retarget provisioning:

```powershell
azd ai agent init --project-id <PROJECT_ARM_ID>
```

The first deploy often takes longer than `azd`'s 20-minute wait. A timeout message does not mean
failure — the agent usually keeps activating in Azure. Wait longer with:

```powershell
azd deploy --timeout 2400
```

Confirm it answers before publishing:

```powershell
azd ai agent invoke --agent contoso-support-agent --message "Reply with the single word: ping"
```

## Publish to Teams

From the **repository root**:

```powershell
./scripts/Publish-AgentToTeams.ps1 -ResourceGroup <RESOURCE_GROUP> `
  -AgentName contoso-support-agent -BotName <UNIQUE_BOT_NAME> `
  -ProjectEndpoint https://<FOUNDRY_ACCOUNT>.services.ai.azure.com/api/projects/<PROJECT> -UseM365PublicEndpoint
```

Azure Bot names are **globally unique**, so pass a `-BotName` that is unlikely to collide. Open the
agent in Teams and send it a message. Drop `-UseM365PublicEndpoint` when the project allows public
network access — the publish API enables the activity protocol on its own.

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| `azd up` created a new resource group and project | That is the default. Target an existing project with `azd ai agent init --project-id <PROJECT_ARM_ID>`. |
| `deployment of service ... timed out after 1200 seconds` | `azd` stopped waiting; the agent usually still activates. Check its status, or re-run with `azd deploy --timeout 2400`. |
| `The bot name is already registered to another bot application` | Azure Bot names are globally unique. Pass a unique `-BotName`. |
| `azd up` cannot find the model | The deployment name in [azure.yaml](azure.yaml) does not exist in the project. Edit it, or let `azd` create it. |
| Agent returns an authorization error | Grant the agent identity **Foundry User** at project scope for model access. |
| No reply in Teams | See the [publishing troubleshooting table](../../../README.md#troubleshooting). |

## Next steps

- Publish and verify — [repository README](../../../README.md)
- Add per-user SharePoint retrieval — [sharepoint-copilot-retrieval](../sharepoint-copilot-retrieval/README.md)
- Pick a tool-grounded sample — [guides/agent-tool-support-matrix.md](../../../guides/agent-tool-support-matrix.md)
- A hardened variant of this host (tolerates transient history failures) — [SharePoint retrieval agent](../sharepoint-copilot-retrieval/agent-framework-agent-with-foundry-toolbox-responses/src/agent-framework-agent-sharepoint-copilot-retrieval/main.py)
