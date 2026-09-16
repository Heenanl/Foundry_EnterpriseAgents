# Copyright (c) Microsoft. All rights reserved.
"""Calls the deployed Foundry hosted agent's Responses endpoint AS the signed-in user.

The bot authenticates to Foundry with its OWN identity (managed identity / app credential,
holding Foundry Agent Consumer), and passes the end user's context on two headers that the
platform forwards to the hosted container unchanged (container protocol 2.0.0):

  - ``x-client-user-token``  the user's delegated assertion (aud = the SSO/OBO app). The hosted
                             agent does the On-Behalf-Of exchange to Graph with it — this is the
                             per-user data path we validated.
  - ``x-ms-user-identity``   the user's Entra object id, for per-user session ISOLATION. The bot's
                             identity must hold the custom UserIdentityImpersonation role (see
                             infra/modules/user-impersonation-role.bicep) or Foundry returns 403.

``Authorization`` (the bot's Foundry token) is what Foundry authenticates; it is NOT the user's
token and is never reused downstream.
"""

import httpx
from azure.identity.aio import DefaultAzureCredential

from config import Config


class AgentClient:
    def __init__(self) -> None:
        self._credential = DefaultAzureCredential()
        self._base = Config.FOUNDRY_PROJECT_ENDPOINT.rstrip("/")

    async def ask(self, agent_name: str, user_text: str, user_token: str, user_oid: str) -> str:
        # Per-agent Responses route; the project-level /openai/v1 path treats `model` as a model
        # deployment and returns DeploymentNotFound for an agent name.
        url = f"{self._base}/agents/{agent_name}/endpoint/protocols/openai/responses?api-version=v1"
        foundry_token = (await self._credential.get_token(Config.FOUNDRY_SCOPE)).token
        headers = {
            "Authorization": f"Bearer {foundry_token}",
            "Content-Type": "application/json",
            "x-client-user-token": user_token,
        }
        body = {
            "model": agent_name,  # the hosted-agent name plays the role of the model id
            "input": [{"role": "user", "content": user_text}],
            "store": False,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, headers=headers, json=body)
        if resp.status_code != 200:
            return f"(agent error {resp.status_code}) {resp.text[:500]}"
        return _extract_text(resp.json())

    async def close(self) -> None:
        await self._credential.close()


def _extract_text(payload: dict) -> str:
    """Pull the assistant text out of a Responses payload across minor shape differences."""
    if isinstance(payload.get("output_text"), str) and payload["output_text"]:
        return payload["output_text"]
    parts: list[str] = []
    for item in payload.get("output", []) or []:
        for content in item.get("content", []) or []:
            text = content.get("text")
            if isinstance(text, str):
                parts.append(text)
            elif isinstance(text, dict) and isinstance(text.get("value"), str):
                parts.append(text["value"])
    return "\n".join(parts).strip() or "(no response)"
