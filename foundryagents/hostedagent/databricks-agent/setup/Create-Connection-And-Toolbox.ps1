<#
.SYNOPSIS
  Creates everything the hosted Databricks Genie agent needs, in code (no portal clicks):
  the Entra app used for OAuth identity passthrough, the Foundry OAuth2 CONNECTION to the
  Genie remote MCP server, and the TOOLBOX that wraps it.

  Steps performed:
    1. Register an Entra app with delegated `user_impersonation` on Azure Databricks
       (resource 2ff814a6-3304-4ab8-85cb-cd0e6f879c1d) + Microsoft Graph `offline_access`,
       and mint a client secret.
    2. azd ai connection create (kind remote-tool, auth-type oauth2) -> DatabricksGenie
    3. Read the per-connection reply URL Foundry generated (ARM control plane) and register it
       on the app, so consent doesn't fail with a redirect_uri mismatch.
    4. azd ai toolbox create databricks-tools --from-file toolbox.yaml

.DESCRIPTION
  This is the *custom* OAuth2 identity-passthrough route. It is deliberately NOT the managed
  Databricks catalog connector (`foundrydatabricksmcp`): managed-provider connections expose no
  `scopes` field (`scopes: null`) and no authorize/token endpoints, so `offline_access` cannot be
  requested and Foundry never refreshes the token.

  Re-running is safe: the app is reused if it already exists, and a new secret is only minted when
  one is not supplied via -ClientSecret.

.NOTES
  Requires: az login (correct tenant), azd >= 1.27.1 with `azd ext install microsoft.foundry`.
  The signing-in account needs permission to create Entra app registrations. Granting admin consent
  is NOT required if the tenant permits user consent for these delegated scopes — each user consents
  on first use, which is the behaviour this sample exercises.

.EXAMPLE
  ./Create-Connection-And-Toolbox.ps1 `
      -ProjectEndpoint https://<FOUNDRY_ACCOUNT>.services.ai.azure.com/api/projects/<PROJECT> `
      -SubscriptionId <SUBSCRIPTION_ID> -ResourceGroup <RESOURCE_GROUP> `
      -AccountName <FOUNDRY_ACCOUNT> -ProjectName <PROJECT> `
      -DatabricksHost adb-<workspace-id>.<n>.azuredatabricks.net `
      -GenieSpaceId <GENIE_SPACE_ID>
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$ProjectEndpoint,   # https://<account>.services.ai.azure.com/api/projects/<project>
  [Parameter(Mandatory)][string]$SubscriptionId,
  [Parameter(Mandatory)][string]$ResourceGroup,
  [Parameter(Mandatory)][string]$AccountName,       # Foundry (AI Services) account name
  [Parameter(Mandatory)][string]$ProjectName,
  [Parameter(Mandatory)][string]$DatabricksHost,    # adb-<workspace-id>.<n>.azuredatabricks.net
  [Parameter(Mandatory)][string]$GenieSpaceId,      # Genie space the agent queries

  [string]$TenantId = (az account show --query tenantId -o tsv),
  [string]$AppDisplayName = "databricks-genie-passthrough",
  [string]$ClientSecret,                            # supply to reuse an existing secret
  # Kept short: Foundry derives a longer per-user name from it, capped at 96 characters.
  [ValidateLength(1, 20)]
  [string]$ConnectionName = "DatabricksGenie",
  [string]$ToolboxName = "databricks-tools",
  [string]$ToolboxFile = (Join-Path $PSScriptRoot "..\agent-framework-agent-databricks\toolbox.yaml")
)
$ErrorActionPreference = "Stop"

# Well-known ids (stable across tenants).
$DATABRICKS_RESOURCE_APP_ID = "2ff814a6-3304-4ab8-85cb-cd0e6f879c1d"
$DATABRICKS_USER_IMPERSONATION = "739272be-e143-11e8-9f32-f2801f1b9fd1"  # delegated scope
$GRAPH_APP_ID = "00000003-0000-0000-c000-000000000000"
$GRAPH_OFFLINE_ACCESS = "7427e0e9-2fba-42fe-b0c0-848c9e6a8182"           # delegated scope

$target   = "https://$DatabricksHost/api/2.0/mcp/genie/$GenieSpaceId"
$authUrl  = "https://login.microsoftonline.com/$TenantId/oauth2/v2.0/authorize"
$tokenUrl = "https://login.microsoftonline.com/$TenantId/oauth2/v2.0/token"
# offline_access lets Foundry refresh the token; without it users re-consent on expiry.
$scopes   = "$DATABRICKS_RESOURCE_APP_ID/user_impersonation,offline_access"

# 1) Register (or reuse) the Entra app that fronts the passthrough connection.
$appId = az ad app list --filter "displayName eq '$AppDisplayName'" --query "[0].appId" -o tsv
if ($appId) {
  Write-Host "Reusing existing app '$AppDisplayName' ($appId)"
}
else {
  Write-Host "Registering Entra app '$AppDisplayName' ..."
  $appId = az ad app create --display-name $AppDisplayName --sign-in-audience AzureADMyOrg --query appId -o tsv
  if (-not $appId) { throw "Could not create the Entra app '$AppDisplayName'." }
}

Write-Host "Setting delegated permissions (Databricks user_impersonation, Graph offline_access) ..."
$requiredResourceAccess = @(
  @{ resourceAppId = $DATABRICKS_RESOURCE_APP_ID; resourceAccess = @(@{ id = $DATABRICKS_USER_IMPERSONATION; type = 'Scope' }) },
  @{ resourceAppId = $GRAPH_APP_ID;               resourceAccess = @(@{ id = $GRAPH_OFFLINE_ACCESS;         type = 'Scope' }) }
)
# az wants this as a file: inline JSON is mangled by PowerShell quoting.
$rraFile = Join-Path ([System.IO.Path]::GetTempPath()) ("rra-{0}.json" -f [guid]::NewGuid())
try {
  $json = ConvertTo-Json -InputObject $requiredResourceAccess -Depth 6
  [System.IO.File]::WriteAllText($rraFile, $json, (New-Object System.Text.UTF8Encoding($false)))
  az ad app update --id $appId --required-resource-accesses "@$rraFile"
  if ($LASTEXITCODE -ne 0) { throw "Could not set required resource access on app $appId." }
}
finally {
  Remove-Item $rraFile -ErrorAction SilentlyContinue
}

if (-not $ClientSecret) {
  Write-Host "Minting a client secret ..."
  $ClientSecret = az ad app credential reset --id $appId --append --display-name "foundry-connection" --years 1 --query password -o tsv
  if (-not $ClientSecret) { throw "Could not mint a client secret for app $appId." }
  Write-Warning "A new client secret was created. It is used only for this run and is not written to disk."
}

# 2) Create the OAuth2 identity-passthrough connection.
Write-Host "Creating connection $ConnectionName -> $target ..."
azd ai connection create $ConnectionName `
  --kind remote-tool `
  --target $target `
  --auth-type oauth2 `
  --client-id $appId `
  --client-secret $ClientSecret `
  --authorization-url $authUrl `
  --token-url $tokenUrl `
  --scopes $scopes `
  --project-endpoint $ProjectEndpoint
if ($LASTEXITCODE -ne 0) { throw "Connection '$ConnectionName' creation failed." }

# 3) Read the reply URL Foundry generated for this connection and register it on the app.
#    `azd ai connection show` does not surface it, so read the ARM control plane.
$connUrl = "https://management.azure.com/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.CognitiveServices/accounts/$AccountName/projects/$ProjectName/connections/${ConnectionName}?api-version=2025-06-01"
$replyUrl = az rest --method get --url $connUrl --query "properties.redirectUrl" -o tsv
if (-not $replyUrl) { throw "Could not read the connection reply URL from $connUrl" }
Write-Host "Foundry reply URL: $replyUrl"

# az replaces the whole list, so merge with what is already registered.
$existing = az ad app show --id $appId --query "web.redirectUris" -o json | ConvertFrom-Json
$all = @(@($existing) + @($replyUrl) | Where-Object { $_ } | Select-Object -Unique)
az ad app update --id $appId --web-redirect-uris $all
if ($LASTEXITCODE -ne 0) { throw "Could not register the reply URL on app $appId." }
$verify = @(az ad app show --id $appId --query "web.redirectUris" -o json | ConvertFrom-Json)
if ($verify -notcontains $replyUrl) {
  throw "Reply URL is not registered on app $appId; consent would fail with a redirect_uri mismatch."
}
Write-Host "Registered reply URL on app $appId"

# 4) Create the toolbox that wraps the connection.
Write-Host "Creating toolbox $ToolboxName from $ToolboxFile ..."
# toolbox.yaml ships placeholders so it reads as documentation on its own.
$spec = (Get-Content -Raw $ToolboxFile) `
  -replace '<databricks-workspace-host>', $DatabricksHost `
  -replace '<genie-space-id>', $GenieSpaceId
# Bind to the connection this run actually created; the file hardcodes the default name.
$spec = $spec -replace '(?m)^(\s*project_connection_id:\s*).+$', "`${1}$ConnectionName"
# azd rejects any extension other than .yaml/.yml, so don't use New-TemporaryFile here.
$specFile = Join-Path ([System.IO.Path]::GetTempPath()) ("toolbox-{0}.yaml" -f [guid]::NewGuid())
try {
  [System.IO.File]::WriteAllText($specFile, $spec, (New-Object System.Text.UTF8Encoding($false)))
  azd ai toolbox create $ToolboxName --from-file $specFile --project-endpoint $ProjectEndpoint
  if ($LASTEXITCODE -ne 0) { throw "Toolbox '$ToolboxName' creation failed." }
}
finally {
  Remove-Item $specFile -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "===== done =====" -ForegroundColor Green
Write-Host "App        : $AppDisplayName ($appId)"
Write-Host "Connection : $ConnectionName"
Write-Host "Toolbox    : $ToolboxName"
Write-Host "Next: deploy the hosted agent (README 'Deploy' step 2), publish to Teams, then invoke and complete the one-time consent."
