# Copyright (c) Microsoft. All rights reserved.
"""Minimal Agent Framework hosted agent, ready to publish to Teams and Microsoft 365."""

import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential


def create_agent(credential):
    project_endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"].rstrip("/")
    client = FoundryChatClient(
        project_endpoint=project_endpoint,
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=credential,
    )
    return Agent(
        client=client,
        instructions=(
            "You are Contoso's support assistant. Answer clearly and concisely. "
            "If you do not know something, say so instead of guessing."
        ),
    )


def main():
    from azure.ai.agentserver.core.tasks import set_resilient_tasks_enabled

    # The platform issues store=true requests; the host rejects them without this.
    set_resilient_tasks_enabled(True)
    credential = DefaultAzureCredential()
    ResponsesHostServer(create_agent(credential)).run()


if __name__ == "__main__":
    main()
