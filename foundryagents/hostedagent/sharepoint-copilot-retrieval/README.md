# Per-user SharePoint retrieval from a Teams-published Foundry hosted agent

Two working approaches to answer from SharePoint, **trimmed to each signed-in Teams user's
permissions**, from a Foundry hosted agent published to Microsoft Teams.

| Path | Approach | Per-user? | Custom bot? |
| --- | --- | --- | --- |
| **[pathB/](pathB/README.md)** *(recommended)* | Shared Teams bot + `x-client-user-token` → in-code OBO | ✅ verified | one shared bot |
| **[pathA/](pathA/README.md)** | Foundry Toolbox OAuth passthrough → OBO gateway | ⚠️ not in testing (shared token) | none (auto-bot) |

Start with the **[decision matrix](../../../guides/per-user-sharepoint-obo-teams-decision-matrix.md)**
for pros/cons, the product-group roadmap, and how to verify per-user isolation yourself.
