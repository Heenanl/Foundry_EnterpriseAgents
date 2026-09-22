# Verify per-user isolation

Run this before rolling out any per-user retrieval agent. It checks that the agent retrieves **as the
signed-in user**, and that a user without access receives nothing.

Applies to [Path A](../foundryagents/hostedagent/sharepoint-copilot-retrieval/pathA/README.md), the
supported per-user SharePoint route.

## Checklist

1. Select **User A** with access and **User B** without access to a known document in the configured
   site. Verify those permissions directly in SharePoint. Give both users the required service
   licenses so licensing differences do not mask authorization behavior.
2. Use separate signed-in browser/Teams profiles and separate new conversations. Record the agent
   version, project, site filter, public-access setting, consent flow, and caller role scopes.
   Never reuse a conversation or response ID across users.
3. Have each user complete tool consent as needed and invoke `whoami`; compare the **actual tool
   output** with the expected account. Never display bearer tokens or send them to the model. A
   model's identity claim is not authentication evidence.
4. Ask the same document-specific question and request a summary as each user. User A should receive
   relevant extracts and citations. User B must receive **no protected extracts, summary, or content**.
   Zero hits or access denial can be valid outcomes; a `403` alone is inconclusive because permissions,
   consent, and licensing can also cause it. If User A receives no hits, fix the positive control first.
5. Inspect retrieval outputs and sanitized service diagnostics, not only final answers or citation-link
   access. Correlate requests using available call/session IDs. Gateway-direct or direct-agent harness
   checks are useful controls, but repeat the full **Teams** route as well.
6. Alternate users, repeat after sign-out/sign-in, and exercise each allowed agent. Verify missing or
   invalid credentials fail closed and that changing agents does not expose another user's context.
   In a non-production environment, validate permission changes after expected propagation delays.
7. For private-only deployment, repeat with public access disabled and the intended DNS/egress routes.
   Validate Toolbox/gateway reachability separately from the inbound Teams route. A public-path pass
   is not evidence for private-only operation.
8. Stop rollout on unexpected identities or content. Revalidate after changes to permissions,
   consent, SDKs, agent versions, session handling, token caches, or networking. Passing this checklist
   is not a security certification or a guarantee that all isolation defects are absent.

## Next steps

- Deploy the route — [Path A](../foundryagents/hostedagent/sharepoint-copilot-retrieval/pathA/README.md)
- Compare agent grounding options — [agent-tool-support-matrix.md](agent-tool-support-matrix.md)
