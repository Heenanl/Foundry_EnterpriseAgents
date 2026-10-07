# Verify per-user isolation

Run this before rolling out any per-user agent. It confirms the agent retrieves **as the signed-in
user**, and that a user without access gets nothing.

Applies to the [SharePoint knowledge base](../foundryagents/hostedagent/sharepoint-knowledge-base/README.md)
(recommended), [Databricks Genie](../foundryagents/hostedagent/databricks-agent/README.md),
[Work IQ](../foundryagents/hostedagent/sharepoint-agent-workiq/README.md), and
[SharePoint retrieval](../foundryagents/hostedagent/sharepoint-copilot-retrieval/README.md) samples.

## Checklist

1. Pick **User A** with access and **User B** without access to a known document or table. Confirm
   the permissions in the source system. Give both users the same licences so licensing does not
   mask the result.
2. Use separate browser or Teams profiles and a **new conversation** for each user. Never reuse a
   conversation across users.
3. Ask the same question as each user. User A gets the content with citations. User B gets **no
   protected content**. If User A gets nothing, fix that first.
4. Confirm identity from the source system, not from the model's answer. For example, check
   SharePoint or Databricks query history for which user ran each request.
5. Alternate users and repeat after signing out and in. Confirm missing or invalid credentials fail
   closed.
6. Repeat the full **Teams** route, not only direct API calls.
7. Revalidate after changes to permissions, SDKs, agent versions, or networking.

Passing this checklist is evidence, not a security certification.

## Learn more

- [Agent tool support matrix](agent-tool-support-matrix.md)
