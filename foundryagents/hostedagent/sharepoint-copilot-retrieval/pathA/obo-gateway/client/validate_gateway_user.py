# Copyright (c) Microsoft. All rights reserved.
"""Per-user proof for the MCP-OBO gateway.

Signs a SPECIFIC end user in via MSAL device-code flow (no password touches this process or
the az session), acquires a REAL delegated token for the gateway's `access_as_user` scope,
prints the token's identity claims, then calls `whoami` and `sharepoint_retrieve`.

Run it once signed in as admin and once as the test user. Expected per-user proof:
  - whoami echoes the DEVICE-CODE user (admin -> admin, testuser -> testuser), NOT a shared identity.
  - sharepoint_retrieve is TRIMMED to what that user can see (admin -> TestSite content;
    testuser with no TestSite access -> no hits / access-scoped empty).

Env:
  GATEWAY_CLIENT_ID  gateway app id (audience of the token)   [required]
  GATEWAY_URL        gateway /mcp URL                          [required]
  TENANT_ID          Entra tenant id                            [required]
  PUBLIC_CLIENT_ID   public client for device code; defaults to Azure CLI (04b07795),
                     which the gateway app pre-authorizes for access_as_user.
"""

import asyncio
import base64
import json
import os
import sys

import msal
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

AZ_CLI_PUBLIC_CLIENT = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"


def _claims(token: str) -> dict:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def _device_code_token(tenant: str, public_client: str, scope: str) -> str:
    app = msal.PublicClientApplication(
        public_client, authority=f"https://login.microsoftonline.com/{tenant}"
    )
    flow = app.initiate_device_flow(scopes=[scope])
    if "user_code" not in flow:
        print("Failed to start device flow:", flow, file=sys.stderr)
        sys.exit(1)
    print("\n" + flow["message"] + "\n", flush=True)  # sign in as the user you want to test
    result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        print("Device auth failed:", result.get("error_description", result), file=sys.stderr)
        sys.exit(1)
    return result["access_token"]


async def main() -> None:
    app_id = os.environ["GATEWAY_CLIENT_ID"]
    url = os.environ["GATEWAY_URL"]
    tenant = os.environ["TENANT_ID"]
    public_client = os.environ.get("PUBLIC_CLIENT_ID", AZ_CLI_PUBLIC_CLIENT)

    token = _device_code_token(tenant, public_client, f"api://{app_id}/access_as_user")
    c = _claims(token)
    print(f"TOKEN identity -> upn={c.get('upn') or c.get('preferred_username')} "
          f"oid={c.get('oid')} scp={c.get('scp')} aud={c.get('aud')}")

    transport = StreamableHttpTransport(url, headers={"Authorization": f"Bearer {token}"})
    async with Client(transport) as client:
        print("tools:", [t.name for t in await client.list_tools()])
        who = await client.call_tool("whoami", {})
        print("whoami:", who.data)
        query = os.environ.get("QUERY", "What is in this site?")
        try:
            res = await client.call_tool("sharepoint_retrieve", {"query": query})
            print(f"sharepoint_retrieve [{query}]:", res.data)
        except Exception as e:  # noqa: BLE001 - surface the exact downstream failure
            print("sharepoint_retrieve error:", e)


if __name__ == "__main__":
    asyncio.run(main())
