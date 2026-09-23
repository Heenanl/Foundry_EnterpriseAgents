# Tests

Offline checks for the Microsoft 365 public-endpoint patch. No Azure resources or credentials
required:

```powershell
pwsh tests/Test-M365AgentEndpoint.ps1
```

These pin the behavior of [scripts/M365AgentEndpoint.psm1](../scripts/M365AgentEndpoint.psm1).
`PATCH /agents/{agent}` replaces the whole `protocol_configuration` and `authorization_schemes` bags,
so the tests assert that every existing protocol and scheme survives the patch, that `activity` is
added when missing, that a single Bot Service scheme stays authoritative, that an existing scheme is
preserved when none is requested, and that the flag can be rolled back.

Routing checks for the archived API Management bridge live in
[deprecated/apim-bridge/tests](../deprecated/apim-bridge/tests/README.md).
