# Copyright (c) Microsoft. All rights reserved.
"""Confidential-client On-Behalf-Of exchange (gbelenky pattern).

The hosted agent receives the signed-in user's delegated assertion (``token B``, audienced to the
OBO app) via the ``x-client-user-token`` header the Foundry gateway forwards unchanged. Here we
exchange it for a delegated Microsoft Graph token (``token D``) using the OBO app's confidential
client credential — standard RFC-7523 ``jwt-bearer`` OBO, no Toolbox, no blueprint/FMI.

Env:
  OBO_CLIENT_ID      the confidential client / OBO API app id (also token B's audience)
  OBO_CLIENT_SECRET  its client secret (Key Vault in prod)
  OBO_TENANT_ID      tenant (falls back to TENANT_ID)
  GRAPH_SCOPE        default https://graph.microsoft.com/.default
"""

import os

import httpx

_TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
_GRAPH_SCOPE = os.getenv("GRAPH_SCOPE", "https://graph.microsoft.com/.default")
_CLIENT_ID = os.getenv("OBO_CLIENT_ID", "")
_CLIENT_SECRET = os.getenv("OBO_CLIENT_SECRET", "")
_TENANT = os.getenv("OBO_TENANT_ID") or os.getenv("TENANT_ID", "")


class ConfidentialObo:
    """Exchanges a user assertion (aud = OBO app) for a delegated Graph token."""

    async def graph_token_for_user(self, user_token: str) -> str:
        if not (_CLIENT_ID and _CLIENT_SECRET and _TENANT):
            raise RuntimeError("OBO env not configured (OBO_CLIENT_ID/SECRET, tenant).")
        form = {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "client_id": _CLIENT_ID,
            "client_secret": _CLIENT_SECRET,
            "assertion": user_token,
            "requested_token_use": "on_behalf_of",
            "scope": _GRAPH_SCOPE,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(_TOKEN_URL.format(tenant=_TENANT), data=form)
        if resp.status_code != 200:
            raise RuntimeError(f"OBO {resp.status_code}: {resp.text[:300]}")
        return resp.json()["access_token"]
