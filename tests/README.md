# Tests

Offline checks for the Microsoft 365 public-endpoint patch, plus optional routing checks for the
[API Management bridge](../README.md#appendix--api-management-bridge).

## Endpoint patch checks (offline)

No Azure resources or credentials required:

```powershell
pwsh tests/Test-M365AgentEndpoint.ps1
```

These pin the behavior of [scripts/M365AgentEndpoint.psm1](../scripts/M365AgentEndpoint.psm1).
`PATCH /agents/{agent}` replaces the whole `protocol_configuration` and `authorization_schemes` bags,
so the tests assert that every existing protocol and scheme survives the patch, that `activity` is
added when missing, that a single Bot Service scheme stays authoritative, and that the flag can be
rolled back.

## Bridge routing checks (optional)

Only needed if you run the optional
[API Management bridge](../README.md#appendix--api-management-bridge). Agents published over the
native Microsoft 365 route do not use these.

### Setup

```powershell
# From the repo root
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r tests/requirements.txt
```

### Configure

```powershell
Copy-Item tests/.env.template tests/.env
# Edit tests/.env with your gateway URL, project, and agent
```

Load the env vars (PowerShell):

```powershell
Get-Content tests/.env | Where-Object { $_ -and $_ -notmatch '^\s*#' } | ForEach-Object {
    $k, $v = $_ -split '=', 2
    [System.Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim())
}
```

### Run

```powershell
python tests/test_bridge.py
```

Or with pytest:

```powershell
pip install pytest
pytest tests/test_bridge.py -v
```

### Interpreting results

| Status | Meaning | Result |
|---|---|---|
| **401** | Routed to Foundry; unsigned probe challenged by auth layer | ✅ PASS |
| 404 | Wrong APIM path/operation | ❌ FAIL |
| 500 | APIM cannot resolve/reach the private backend (DNS/VNet) | ❌ FAIL |
| 400 | Reached Foundry but request rejected (e.g. missing `api-version`) | ❌ FAIL |

> The test uses an **unsigned** request on purpose. A correctly routed unsigned
> request is challenged with **401** because Foundry validates the Bot Framework
> JWT itself. Real Bot Service traffic carries a valid JWT and returns **202**,
> with the agent reply delivered asynchronously via the Bot Service `serviceUrl`.
