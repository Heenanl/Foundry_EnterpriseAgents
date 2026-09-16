<#
.SYNOPSIS
  Configures an Entra app registration as a Microsoft Teams SSO target so Teams can do
  SILENT single sign-on (signin/tokenExchange) with NO consent popup, and the bot/agent
  can exchange the SSO token for a downstream (Graph / gateway) token via OBO.

  This is the "use the customer's app for silent SSO to avoid consent popups" pattern:
  Teams only performs silent SSO when the app is registered exactly this way — an
  Application ID URI of api://botid-<appId>, an exposed access_as_user scope, the Teams
  first-party clients pre-authorized, and id+access token issuance enabled. Anything else
  falls back to an interactive consent/sign-in card.

.DESCRIPTION
  Applies (idempotently) to the app you pass in -AppId:
    - requestedAccessTokenVersion = 2, signInAudience = AzureADMyOrg (single tenant)
    - identifierUri = api://botid-<appId>   (Teams enforces the botid- match on the SSO resource)
    - exposed delegated scope: access_as_user
    - pre-authorized Teams first-party clients (desktop/mobile + web) for that scope
    - web.implicitGrantSettings id+access token issuance = true
        (without these Teams getAuthToken returns signin/failure {"code":"invokeerror"})
    - Bot Framework reply URL https://token.botframework.com/.auth/web/redirect
    - optional claim idtyp on the access token
    - (optional) a downstream delegated permission the OBO step will request, e.g. the
      gateway's api://<gateway-appId>/access_as_user  (pass -DownstreamResourceAppId /
      -DownstreamScopeId), then admin consent.

  Use the SAME app as the Azure Bot's msaAppId (the bot/SSO app), NOT the gateway API app.
  The bot's OAuth Connection Setting (teams-sso) uses this app's client id/secret and this
  same tokenExchangeUrl (api://botid-<appId>).

.NOTES
  Requires an Entra admin. Idempotent: re-running only adds what is missing.
  Mirrors the msft-mfg-ai ensure_app_sso / preprovision-sso-app pattern.
#>
[CmdletBinding()]
param(
  # The bot / SSO app registration (Azure Bot msaAppId). Required.
  [Parameter(Mandatory = $true)]
  [string]$AppId,

  # Downstream API whose delegated scope the OBO step will request (e.g. the MCP-OBO gateway app).
  # Leave empty to only configure Teams SSO without granting a downstream permission.
  [string]$DownstreamResourceAppId = "",

  # The delegated scope id (GUID) of $DownstreamResourceAppId to grant (e.g. its access_as_user id).
  [string]$DownstreamScopeId = "",

  # Grant admin consent at the end (needs a tenant admin).
  [switch]$AdminConsent
)
$ErrorActionPreference = "Stop"

# Teams first-party client app IDs that must be pre-authorized for silent SSO.
$TeamsDesktopMobile = "1fec8e78-bce4-4aaf-ab1b-5451cc387264"
$TeamsWeb           = "5e3ce6c0-2b1f-4285-8d4b-75ee78787346"
$BfReplyUrl         = "https://token.botframework.com/.auth/web/redirect"

Write-Host "Tenant:" (az account show --query tenantId -o tsv)
Write-Host "Configuring Teams SSO on app $AppId"

$objectId = az ad app show --id $AppId --query id -o tsv
if (-not $objectId) { throw "App $AppId not found." }

# Helper: PATCH the application via Graph using a temp JSON file (reliable quoting on PowerShell).
function Patch-App([string]$oid, $bodyObj) {
  $f = New-TemporaryFile
  ($bodyObj | ConvertTo-Json -Depth 12) | Set-Content -Path $f -Encoding utf8
  az rest --method PATCH --uri "https://graph.microsoft.com/v1.0/applications/$oid" `
    --headers "Content-Type=application/json" --body "@$f" | Out-Null
  Remove-Item $f -Force
}

# 1) v2 tokens + single-tenant sign-in audience.
Patch-App $objectId @{
  api           = @{ requestedAccessTokenVersion = 2 }
  signInAudience = "AzureADMyOrg"
}
Write-Host "Set requestedAccessTokenVersion=2, signInAudience=AzureADMyOrg"

# 2) Application ID URI = api://botid-<appId> (Teams silent-SSO resource-match requirement).
$identifierUri = "api://botid-$AppId"
$currentUris = (az ad app show --id $AppId --query "identifierUris" -o tsv) -split "`n" | Where-Object { $_ }
if ($currentUris -notcontains $identifierUri) {
  Patch-App $objectId @{ identifierUris = @($identifierUri) }
  Write-Host "Set identifierUri $identifierUri"
} else {
  Write-Host "identifierUri already set ($identifierUri)"
}

# 3) Expose access_as_user (reuse the scope id if it already exists).
$scopeId = az ad app show --id $AppId --query "api.oauth2PermissionScopes[?value=='access_as_user'].id | [0]" -o tsv
if (-not $scopeId) { $scopeId = [guid]::NewGuid().ToString() }
Patch-App $objectId @{
  api = @{
    requestedAccessTokenVersion = 2
    oauth2PermissionScopes = @(@{
      id                      = $scopeId
      value                   = "access_as_user"
      type                    = "User"
      isEnabled               = $true
      adminConsentDisplayName = "Access the Teams agent as the signed-in user"
      adminConsentDescription = "Allows the Teams agent to act on behalf of the signed-in user."
      userConsentDisplayName  = "Access the agent on your behalf"
      userConsentDescription  = "Allows the agent to act on your behalf."
    })
  }
}
Write-Host "Exposed scope access_as_user ($scopeId)"

# 4) Pre-authorize the Teams first-party clients for that scope (SEPARATE PATCH; validated
#    against scopes that already exist, so must run after the scope is created).
Patch-App $objectId @{
  api = @{ preAuthorizedApplications = @(
    @{ appId = $TeamsDesktopMobile; delegatedPermissionIds = @($scopeId) },
    @{ appId = $TeamsWeb;           delegatedPermissionIds = @($scopeId) }
  ) }
}
Write-Host "Pre-authorized Teams desktop/mobile + web clients"

# 5) Enable id + access token issuance (Teams getAuthToken fails with invokeerror otherwise)
#    and register the Bot Framework reply URL on the web platform.
$currentReplies = (az ad app show --id $AppId --query "web.redirectUris" -o tsv) -split "`n" | Where-Object { $_ }
$replies = @($currentReplies)
if ($replies -notcontains $BfReplyUrl) { $replies += $BfReplyUrl }
Patch-App $objectId @{
  web = @{
    redirectUris          = $replies
    implicitGrantSettings = @{ enableIdTokenIssuance = $true; enableAccessTokenIssuance = $true }
  }
}
Write-Host "Enabled id+access token issuance and registered Bot Framework reply URL"

# 6) Emit idtyp on the access token so the downstream can distinguish app vs user tokens.
Patch-App $objectId @{
  optionalClaims = @{ accessToken = @(@{ name = "idtyp"; essential = $false }) }
}
Write-Host "Added optional claim idtyp (access token)"

# 7) Optional: grant the downstream delegated permission the OBO step requests.
if ($DownstreamResourceAppId -and $DownstreamScopeId) {
  $existing = az ad app show --id $AppId --query "requiredResourceAccess" -o json | ConvertFrom-Json
  $list = @()
  if ($existing) { $list = @($existing) }
  if (-not ($list | Where-Object { $_.resourceAppId -eq $DownstreamResourceAppId })) {
    $list += @{
      resourceAppId  = $DownstreamResourceAppId
      resourceAccess = @(@{ id = $DownstreamScopeId; type = "Scope" })
    }
    Patch-App $objectId @{ requiredResourceAccess = $list }
    Write-Host "Granted downstream delegated permission $DownstreamResourceAppId/$DownstreamScopeId"
  } else {
    Write-Host "Downstream resource $DownstreamResourceAppId already present"
  }
}

# 8) Service principal + optional admin consent.
if (-not (az ad sp show --id $AppId --query id -o tsv 2>$null)) { az ad sp create --id $AppId | Out-Null }
if ($AdminConsent) {
  az ad app permission admin-consent --id $AppId
  Write-Host "Admin consent granted"
} else {
  Write-Host "Skipped admin consent (re-run with -AdminConsent as a tenant admin, or run: az ad app permission admin-consent --id $AppId)"
}

Write-Host ""
Write-Host "===== Teams SSO configuration =====" -ForegroundColor Green
Write-Host "SSO_APP_ID       = $AppId"
Write-Host "SSO_APP_RESOURCE = $identifierUri"
Write-Host "SSO_SCOPE        = api://botid-$AppId/access_as_user"
Write-Host "Bot OAuth connection tokenExchangeUrl = $identifierUri"
Write-Host "==================================="
