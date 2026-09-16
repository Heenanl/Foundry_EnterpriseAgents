# Copyright (c) Microsoft. All rights reserved.
"""SharePoint per-user retrieval hosted agent — x-client-user-token OBO (no toolbox/connection).

The signed-in user's delegated assertion (a token whose audience is this agent's OBO app,
scope ``access_as_user``) is forwarded by the Foundry gateway in the custom
``x-client-user-token`` request header. The platform passes ``x-client-*`` headers through to the
container unchanged (container protocol 2.0.0) and strips ``Authorization``. The agent reads the
assertion, does an On-Behalf-Of exchange to Microsoft Graph, and calls the Microsoft 365 Copilot
Retrieval API scoped to one SharePoint site, so results are permission-trimmed to that user.

No Foundry OAuth connection or toolbox is involved — this pattern avoids the connector-gateway
entirely (mirrors gbelenky/HostedOBOAgent and maurominella/hosted_agents). A caller that has the
user's assertion (a Teams SSO bot, or a client acquiring it via MSAL) sends it in the header.
"""

import asyncio
import contextvars
import logging
import os

import httpx
import msal
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Foundry lowercases forwarded header keys; keep the lookup lowercase.
CLIENT_USER_TOKEN_HEADER = os.getenv("CLIENT_USER_TOKEN_HEADER", "x-client-user-token").lower()
GRAPH_SCOPES = [
    "https://graph.microsoft.com/Files.Read.All",
    "https://graph.microsoft.com/Sites.Read.All",
]
RETRIEVAL_URL = os.getenv("RETRIEVAL_API_URL", "https://graph.microsoft.com/v1.0/copilot/retrieval")
SITE_URL = os.getenv("SHAREPOINT_SITE_URL", "").rstrip("/")
MAX_RESULTS = int(os.getenv("MAX_RESULTS", "10"))

# Per-request user assertion, kept OUT of LLM-visible tool parameters via a ContextVar:
# the handler stashes it from the header; the tool reads it.
_current_user_assertion: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_user_assertion", default=""
)

_obo_app: msal.ConfidentialClientApplication | None = None


def _get_obo_app() -> msal.ConfidentialClientApplication:
    """Lazily build the confidential client for the OBO exchange (kept out of import time so a
    missing env var never fails container readiness)."""
    global _obo_app
    if _obo_app is None:
        _obo_app = msal.ConfidentialClientApplication(
            os.environ["APP_OBO_CLIENT_ID"],
            client_credential=os.environ["APP_OBO_CLIENT_SECRET"],
            authority=f"https://login.microsoftonline.com/{os.environ['APP_OBO_TENANT_ID']}",
        )
    return _obo_app


async def sharepoint_retrieve(query: str) -> str:
    """Retrieve relevant text extracts from the organization's SharePoint site on behalf of the
    signed-in user (permission-trimmed). Input: a natural-language question."""
    assertion = _current_user_assertion.get("")
    if not assertion:
        return (
            "NO_USER_TOKEN: no signed-in user assertion was forwarded, so per-user SharePoint "
            f"retrieval cannot run. The caller must send the user's token in the "
            f"'{CLIENT_USER_TOKEN_HEADER}' header."
        )

    # On-Behalf-Of: exchange the user's assertion for a delegated Microsoft Graph token.
    result = await asyncio.to_thread(
        _get_obo_app().acquire_token_on_behalf_of,
        user_assertion=assertion,
        scopes=GRAPH_SCOPES,
    )
    if "access_token" not in result:
        codes = ", ".join(f"AADSTS{c}" for c in result.get("error_codes", [])) or "no AADSTS code"
        return f"OBO_FAILED: {result.get('error')} ({codes}) - {str(result.get('error_description', ''))[:300]}"
    graph_token = result["access_token"]

    body: dict = {
        "queryString": (query or "")[:1500] or "Summarize the most relevant document.",
        "dataSource": "sharePoint",
        "resourceMetadata": ["title", "author"],
        "maximumNumberOfResults": MAX_RESULTS,
    }
    if SITE_URL:
        body["filterExpression"] = f'path:"{SITE_URL}/"'  # scope to ONE site

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            RETRIEVAL_URL,
            headers={"Authorization": f"Bearer {graph_token}", "Content-Type": "application/json"},
            json=body,
        )
    if resp.status_code != 200:
        return f"RETRIEVAL_ERROR {resp.status_code}: {resp.text[:400]}"

    hits = resp.json().get("retrievalHits", [])
    if not hits:
        return "NO_RESULTS: the Retrieval API returned no extracts for that query on the configured site."

    blocks = []
    for h in hits:
        title = (h.get("resourceMetadata") or {}).get("title") or "(untitled)"
        web_url = h.get("webUrl") or ""
        extracts = [e.get("text") for e in h.get("extracts", []) if e.get("text")]
        blocks.append(f"### {title}\n{web_url}\n" + "\n".join(extracts))
    return "\n\n".join(blocks)


class _ResilientResponsesHostServer(ResponsesHostServer):
    """Stashes the forwarded user assertion into a ContextVar and hardens history fetch.

    The built-in ``_handle_inner_agent`` calls ``await context.get_history()`` unconditionally;
    when the platform issues a ``store=true`` request that fetch can raise inside the SDK and bubble
    up as a ``server_error``. We wrap ``get_history`` so a transient failure degrades to "no prior
    turns", and we read ``context.client_headers`` here (the SDK populates it from the inbound
    ``x-client-*`` headers) to capture the user assertion before the agent runs.
    """

    async def _handle_inner_agent(self, *args, **kwargs):  # type: ignore[override]
        context = next(
            (a for a in (*args, *kwargs.values()) if hasattr(a, "get_history")),
            None,
        )
        if context is not None:
            headers = getattr(context, "client_headers", None) or {}
            assertion = ""
            try:
                assertion = headers.get(CLIENT_USER_TOKEN_HEADER, "")
            except Exception:  # noqa: BLE001 - headers may be an unexpected type
                assertion = ""
            _current_user_assertion.set(assertion or "")
            logger.info("user assertion present=%s len=%d", bool(assertion), len(assertion or ""))

            original_get_history = context.get_history

            async def safe_get_history(_orig=original_get_history):
                try:
                    return await _orig()
                except Exception as ex:  # noqa: BLE001 - intentional broad catch
                    logger.warning(
                        "context.get_history() failed (%s); proceeding with no prior history.", ex
                    )
                    return []

            try:
                context.get_history = safe_get_history  # type: ignore[method-assign]
            except Exception:  # noqa: BLE001 - some contexts are read-only
                pass

        async for item in super()._handle_inner_agent(*args, **kwargs):
            yield item


def main():
    # The deployed responses SDK requires the resilient-task subsystem for store=true requests
    # (the platform issues these); without it the host fails every /responses call.
    try:
        from azure.ai.agentserver.core.tasks import set_resilient_tasks_enabled

        set_resilient_tasks_enabled(True)
    except Exception:  # noqa: BLE001 - best-effort
        logger.warning("Could not enable resilient tasks", exc_info=True)

    credential = DefaultAzureCredential()

    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=credential,
    )

    agent = Agent(
        client=client,
        instructions=(
            "You answer questions grounded in the organization's SharePoint content. "
            "Always call the sharepoint_retrieve tool to fetch relevant extracts, then answer only "
            "from those extracts and cite the source document links. The tool runs on behalf of the "
            "signed-in user and is permission-trimmed, so never infer or reveal content the tool did "
            "not return. If the tool returns NO_RESULTS or an error code, say so plainly rather than "
            "guessing."
        ),
        tools=[sharepoint_retrieve],
        # History is managed by the hosting infrastructure; don't ask the service to store it.
        default_options={"store": False},
    )

    server = _ResilientResponsesHostServer(agent)
    server.run()


if __name__ == "__main__":
    main()
