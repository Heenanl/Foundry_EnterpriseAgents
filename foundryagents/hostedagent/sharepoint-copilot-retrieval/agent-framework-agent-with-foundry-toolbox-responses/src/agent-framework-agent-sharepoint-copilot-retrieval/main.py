# Copyright (c) Microsoft. All rights reserved.
"""Retrieve SharePoint content through Foundry Toolbox.

The SDK authenticates service requests and forwards the platform call ID to the
Toolbox. The OAuth connection handles upstream consent and credentials; only
the gateway performs Graph OBO.
"""

import logging
import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient, FoundryToolbox
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


def create_agent(credential):
    """Use the explicitly configured Toolbox with no local retrieval fallback."""
    project_endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"].rstrip("/")
    toolbox_name = os.environ["TOOLBOX_NAME"]
    toolbox_url = f"{project_endpoint}/toolboxes/{toolbox_name}/mcp?api-version=v1"
    toolbox = FoundryToolbox(credential, url=toolbox_url)
    client = FoundryChatClient(
        project_endpoint=project_endpoint,
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=credential,
    )
    logger.info("Using Foundry Toolbox %s", toolbox_name)
    return Agent(
        client=client,
        instructions=(
            "Use the available SharePoint Toolbox tools for every retrieval request. "
            "Call whoami when asked which user is authenticated. For document questions, "
            "call sharepoint_retrieve and answer only from that turn's returned results, "
            "including titles and source links. Never reuse earlier document content as "
            "evidence of a successful retrieval. Report an empty result or tool failure "
            "honestly. Do not invent results, identities, or sign-in links."
        ),
        tools=toolbox,
        default_options={"store": False},
    )


class _HistorySafeContext:
    def __init__(self, context):
        self._context = context

    def __getattr__(self, name):
        return getattr(self._context, name)

    async def get_history(self):
        try:
            return await self._context.get_history()
        except Exception as ex:  # noqa: BLE001 - history failure must not fail the turn
            logger.warning(
                "context.get_history() failed (%s); proceeding with no prior history.",
                ex,
            )
            return []


class _ResilientResponsesHostServer(ResponsesHostServer):
    """Treat transient platform history failures as an empty conversation."""

    async def _handle_inner_agent(self, *args, **kwargs):  # type: ignore[override]
        context = next(
            (value for value in (*args, *kwargs.values()) if hasattr(value, "get_history")),
            None,
        )
        if context is not None:
            safe_context = _HistorySafeContext(context)
            args = tuple(safe_context if value is context else value for value in args)
            kwargs = {
                name: safe_context if value is context else value
                for name, value in kwargs.items()
            }

        async for item in super()._handle_inner_agent(*args, **kwargs):
            yield item


def main():
    from azure.ai.agentserver.core.tasks import set_resilient_tasks_enabled

    set_resilient_tasks_enabled(True)
    credential = DefaultAzureCredential()
    server = _ResilientResponsesHostServer(create_agent(credential))
    server.run()


if __name__ == "__main__":
    main()
