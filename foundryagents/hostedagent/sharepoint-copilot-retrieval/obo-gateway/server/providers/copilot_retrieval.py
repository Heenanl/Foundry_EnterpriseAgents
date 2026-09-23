# Copyright (c) Microsoft. All rights reserved.
"""Provider: Microsoft 365 Copilot Retrieval API (SharePoint), per-user, site-scoped.

SHAREPOINT_SITE_URL takes one site or a comma-separated list; the sites are combined with KQL `OR`
so a single tool call covers all of them under one consent. The scope is operator-configured — the
tool takes only a query, so the model cannot widen it.

This is the reference provider. To support a different downstream tool that lacks Foundry
server-side OBO, copy this file, change GRAPH_SCOPES + the HTTP call, and register it."""

import logging
import os

import httpx

GRAPH_SCOPES = ["https://graph.microsoft.com/Files.Read.All", "https://graph.microsoft.com/Sites.Read.All"]
RETRIEVAL_URL = os.getenv("RETRIEVAL_API_URL", "https://graph.microsoft.com/v1.0/copilot/retrieval")
SITE_URLS = [s.strip().rstrip("/") for s in os.getenv("SHAREPOINT_SITE_URL", "").split(",") if s.strip()]
MAX_RESULTS = int(os.getenv("MAX_RESULTS", "10"))

# KQL `OR` across sites; the API documents this for multi-site retrieval.
FILTER_EXPRESSION = " OR ".join(f'path:"{u}/"' for u in SITE_URLS)

name = "copilot_retrieval"

logger = logging.getLogger("mcp-obo-gateway")
if FILTER_EXPRESSION:
    logger.info("copilot_retrieval scope: %d site(s) -> %s", len(SITE_URLS), FILTER_EXPRESSION)
else:
    logger.warning(
        "copilot_retrieval scope: NO site filter - retrieval spans every SharePoint site the "
        "signed-in user can access. Set SHAREPOINT_SITE_URL to scope it."
    )


def register(mcp, exchange) -> None:
    @mcp.tool(
        name="sharepoint_retrieve",
        description=(
            "Retrieve relevant text extracts from the configured SharePoint site(s), on behalf of the "
            "signed-in user (permission-trimmed). Input: a natural-language question."
        ),
    )
    async def sharepoint_retrieve(query: str) -> dict:
        graph_token = await exchange(GRAPH_SCOPES)  # OBO -> Graph, done by the gateway
        body: dict = {
            "queryString": (query or "")[:1500] or "Summarize the most relevant document.",
            "dataSource": "sharePoint",
            "resourceMetadata": ["title", "author"],
            "maximumNumberOfResults": MAX_RESULTS,
        }
        if FILTER_EXPRESSION:
            body["filterExpression"] = FILTER_EXPRESSION  # scope to the configured site(s)
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                RETRIEVAL_URL,
                headers={"Authorization": f"Bearer {graph_token}", "Content-Type": "application/json"},
                json=body,
            )
        resp.raise_for_status()
        hits = resp.json().get("retrievalHits", [])
        return {
            "results": [
                {
                    "webUrl": h.get("webUrl"),
                    "title": (h.get("resourceMetadata") or {}).get("title"),
                    "extracts": [e.get("text") for e in h.get("extracts", []) if e.get("text")],
                }
                for h in hits
            ]
        }
