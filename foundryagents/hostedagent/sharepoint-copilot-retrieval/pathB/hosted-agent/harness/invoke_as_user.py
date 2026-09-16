# Copyright (c) Microsoft. All rights reserved.
"""Direct harness for the sp-obo-responses agent (no Teams, no bot).

Mints a REAL per-user delegated token (token B, aud = the OBO app) via MSAL device-code, then POSTs
to the Foundry Responses endpoint forwarding it on `x-client-user-token` exactly as the shared bot
will. Proves the core mechanism: forwarded user token -> in-container confidential OBO -> Copilot
Retrieval, permission-trimmed. Run once as admin (expects the doc) and once as testuser (expects a
denial / no hits).

Env:
  OBO_CLIENT_ID   the OBO app id (token B audience)             [required]
  TENANT_ID       tenant                                         [required]
  PROJECT_ENDPOINT  https://<acct>.services.ai.azure.com/api/projects/<proj>   [required]
  AGENT_NAME      hosted agent name (plays the model id)         [default sp-obo-responses]
  QUERY           the question                                   [default "windows byod"]
  FOUNDRY_TOKEN   pre-fetched ai.azure.com token; else uses `az account get-access-token`
"""

import base64
import json
import os
import subprocess
import sys
import tempfile
import time

import httpx
import msal

AZ_CLI_PUBLIC_CLIENT = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"


def _claims(token: str) -> dict:
    p = token.split(".")[1]
    p += "=" * (-len(p) % 4)
    return json.loads(base64.urlsafe_b64decode(p))


def _device_code_token(tenant: str, scope: str) -> str:
    # Reuse a cached user token (per OBO app) while it's still valid, so redeploy/retest
    # iterations don't force a new device-code sign-in every time.
    cache = os.path.join(tempfile.gettempdir(), f"obo_userB_{os.environ['OBO_CLIENT_ID']}.txt")
    if os.path.exists(cache):
        try:
            cached = open(cache, encoding="utf-8").read().strip()
            if cached and _claims(cached).get("exp", 0) - time.time() > 300:
                print("(reusing cached user token)", flush=True)
                return cached
        except Exception:  # noqa: BLE001
            pass
    app = msal.PublicClientApplication(AZ_CLI_PUBLIC_CLIENT, authority=f"https://login.microsoftonline.com/{tenant}")
    flow = app.initiate_device_flow(scopes=[scope])
    if "user_code" not in flow:
        print("device flow start failed:", flow, file=sys.stderr); sys.exit(1)
    print("\n" + flow["message"] + "\n", flush=True)
    result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        print("device auth failed:", result.get("error_description", result), file=sys.stderr); sys.exit(1)
    token = result["access_token"]
    try:
        open(cache, "w", encoding="utf-8").write(token)
    except Exception:  # noqa: BLE001
        pass
    return token


def _foundry_token() -> str:
    tok = os.environ.get("FOUNDRY_TOKEN")
    if tok:
        return tok
    out = subprocess.run(
        "az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv",
        capture_output=True, text=True, check=True, shell=True,
    )
    return out.stdout.strip()


def main() -> None:
    obo_app = os.environ["OBO_CLIENT_ID"]
    tenant = os.environ["TENANT_ID"]
    endpoint = os.environ["PROJECT_ENDPOINT"].rstrip("/")
    agent = os.environ.get("AGENT_NAME", "sp-obo-responses")
    query = os.environ.get("QUERY", "windows byod")

    user_token = _device_code_token(tenant, f"api://{obo_app}/access_as_user")
    c = _claims(user_token)
    print(f"USER token -> upn={c.get('upn') or c.get('preferred_username')} oid={c.get('oid')} "
          f"scp={c.get('scp')} aud={c.get('aud')}")

    url = f"{endpoint}/agents/{agent}/endpoint/protocols/openai/responses?api-version=v1"
    headers = {
        "Authorization": f"Bearer {_foundry_token()}",
        "Content-Type": "application/json",
        "x-client-user-token": user_token,
    }
    body = {"model": agent, "input": [{"role": "user", "content": query}], "store": False}
    resp = httpx.post(url, headers=headers, json=body, timeout=120.0)
    print("HTTP", resp.status_code)
    try:
        payload = resp.json()
    except Exception:
        print(resp.text[:1000]); return
    # print assistant text
    txt = payload.get("output_text")
    if not txt:
        parts = []
        for item in payload.get("output", []) or []:
            for content in item.get("content", []) or []:
                t = content.get("text")
                if isinstance(t, str):
                    parts.append(t)
                elif isinstance(t, dict) and isinstance(t.get("value"), str):
                    parts.append(t["value"])
        txt = "\n".join(parts)
    print("RESULT:", txt or json.dumps(payload)[:1000])


if __name__ == "__main__":
    main()
