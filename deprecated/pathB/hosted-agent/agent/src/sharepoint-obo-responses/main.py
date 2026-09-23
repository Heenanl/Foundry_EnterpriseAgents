# Copyright (c) Microsoft. All rights reserved.
"""SharePoint per-user retrieval as a Foundry Responses-protocol HOSTED agent.

A shared Teams bot obtains the user's Teams-SSO delegated token and calls this agent's Responses
endpoint, forwarding the token on ``x-client-user-token`` — a header the Foundry gateway passes to
the container unchanged (hosted-agent contract). This agent reads it from ``context.client_headers``
(never from the chat text), exchanges it for a delegated Microsoft Graph token via confidential OBO
(``obo.py``), then calls the Microsoft 365 Copilot Retrieval API AS THAT USER, scoped to one
SharePoint site — so results are permission-trimmed per user. The Toolbox is bypassed entirely,
which is what makes this work when the agent is published to Teams.

Env (see the folder README):
  OBO_CLIENT_ID / OBO_CLIENT_SECRET / OBO_TENANT_ID   the OBO confidential app (= user token audience)
  SHAREPOINT_SITE_URL                                 e.g. https://<t>.sharepoint.com/sites/TestSite
  CLIENT_USER_TOKEN_HEADER                            default x-client-user-token
  SYNTH_MODEL                                         project model deployment for answer synthesis
  RETRIEVAL_API_URL / MAX_RESULTS
"""

import asyncio
import logging
import os
import re

import httpx
from azure.ai.agentserver.responses import (
    ResponseContext,
    ResponsesAgentServerHost,
    ResponsesServerOptions,
    TextResponse,
)
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from obo import ConfidentialObo

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("sharepoint-obo-responses")

RETRIEVAL_URL = os.getenv("RETRIEVAL_API_URL", "https://graph.microsoft.com/v1.0/copilot/retrieval")
SITE_URL = os.getenv("SHAREPOINT_SITE_URL", "").rstrip("/")
MAX_RESULTS = int(os.getenv("MAX_RESULTS", "10"))
USER_TOKEN_HEADER = os.getenv("CLIENT_USER_TOKEN_HEADER", "x-client-user-token").lower()
SYNTH_MODEL = os.getenv("SYNTH_MODEL", "gpt-4.1")

app = ResponsesAgentServerHost(options=ResponsesServerOptions(default_fetch_history_count=10))
_obo = ConfidentialObo()
# The hosted agent calls its project's model with its OWN instance identity (retrieval already
# enforced per-user trimming, so synthesis over those extracts is safe).
_project = AIProjectClient(endpoint=os.environ.get("FOUNDRY_PROJECT_ENDPOINT", ""), credential=DefaultAzureCredential())
_openai = _project.get_openai_client()


def _clean_extract(text: str) -> str:
    """Strip Copilot Retrieval markup (page tags, image placeholders, empty links) for Teams."""
    text = re.sub(r"</?page[^>]*>", "", text)          # <page_1> ... </page_1>
    text = re.sub(r"!\[\]\[[^\]]*\]", "", text)          # ![][image_xxx==] placeholders
    text = re.sub(r"\[([^\]]+)\]\(\s*\)", r"\1", text)   # [text]() empty links -> plain text
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def _retrieve_hits(graph_token: str, query: str) -> tuple[str | None, list]:
    """Run per-user Copilot Retrieval. Returns (message, hits): message set when there is nothing
    to synthesize (denied / error / no hits); otherwise (None, hits)."""
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
    if resp.status_code == 403:
        return "You don't have access to this SharePoint content.", []
    if resp.status_code != 200:
        return f"Retrieval error {resp.status_code}: {resp.text[:300]}", []
    hits = resp.json().get("retrievalHits", [])
    if not hits:
        return "No matching content was found in the site for your question.", []
    return None, hits


def _synth_sync(query: str, context: str) -> str:
    resp = _openai.chat.completions.create(
        model=SYNTH_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You answer questions strictly from the provided SharePoint sources. "
                    "Cite sources inline as [n] matching the numbered sources. If the answer is "
                    "not in the sources, say you couldn't find it. Be concise and use short bullets."
                ),
            },
            {"role": "user", "content": f"Question: {query}\n\nSources:\n{context}"},
        ],
        temperature=0.2,
    )
    return (resp.choices[0].message.content or "").strip()


async def _synthesize(query: str, hits: list) -> str:
    parts, sources = [], []
    for i, h in enumerate(hits[:5], 1):
        title = (h.get("resourceMetadata") or {}).get("title") or "(untitled)"
        url = h.get("webUrl") or ""
        txt = "\n".join(_clean_extract(e.get("text", "")) for e in h.get("extracts", []))
        parts.append(f"[{i}] {title}\n{txt[:2000]}")
        sources.append(f"[{i}] [{title}]({url})" if url else f"[{i}] {title}")
    answer = await asyncio.to_thread(_synth_sync, query, "\n\n".join(parts))
    return f"{answer}\n\n**Sources**\n" + "\n".join(sources)


@app.response_handler
async def handler(request, context: ResponseContext, _cancel) -> TextResponse:
    user_text = await context.get_input_text() or ""
    user_token = (context.client_headers or {}).get(USER_TOKEN_HEADER)
    if not user_token:
        logger.warning("Request missing the '%s' header", USER_TOKEN_HEADER)
        return TextResponse(context, request, text="I couldn't verify your identity. Please sign in and try again.")
    try:
        graph_token = await _obo.graph_token_for_user(user_token)
    except Exception:
        logger.exception("On-behalf-of token exchange failed")
        return TextResponse(context, request, text="I couldn't access your SharePoint content right now. Please try again.")
    try:
        message, hits = await _retrieve_hits(graph_token, user_text)
        if message:
            return TextResponse(context, request, text=message)
        answer = await _synthesize(user_text, hits)
    except Exception:
        logger.exception("Retrieval or synthesis failed")
        answer = "Something went wrong answering from SharePoint. Please try again."
    return TextResponse(context, request, text=answer)


if __name__ == "__main__":
    logger.info("Starting SharePoint OBO Responses agent …")
    app.run()
