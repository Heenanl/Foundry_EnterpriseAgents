<#
.SYNOPSIS
    Enables (or rolls back) Microsoft 365 / Teams traffic to a private-network
    Foundry agent's Activity Protocol route, without an APIM or proxy bridge.

.DESCRIPTION
    Sets `agent_endpoint.protocol_configuration.activity.enable_m365_public_endpoint`.
    Foundry then allows Azure Bot Service and Microsoft 365 source IPs to reach ONLY
    the Activity Protocol route, while the Foundry account keeps
    `publicNetworkAccess=Disabled`. Responses, Invocations, A2A, MCP and the project
    APIs stay private.

    The PATCH replaces the whole `protocol_configuration` and `authorization_schemes`
    bags, so this script reads the agent first and re-sends everything it already had
    (see scripts/M365AgentEndpoint.psm1). It then re-reads the agent and fails if any
    protocol was dropped or the flag did not take.

    The setting changes network reachability, NOT authorization: a Bot Service
    authorization scheme is always kept on the endpoint.

    Run this from a client that can reach the project (the management APIs stay
    governed by the project's network rules).

    Ref: https://learn.microsoft.com/azure/foundry/agents/how-to/publish-copilot-virtual-network

.PARAMETER AgentName
    Foundry agent to update.

.PARAMETER ProjectEndpoint
    https://<account>.services.ai.azure.com/api/projects/<project>
    Alternatively supply -FoundryHost and -ProjectName.

.PARAMETER AuthorizationScheme
    Bot Service scheme to keep on the endpoint. Match the publish scope:
    Shared/Personal -> BotServiceRbac, Tenant -> BotServiceTenant.

.PARAMETER Disable
    Roll back: set enable_m365_public_endpoint to false.

.PARAMETER WhatIf
    Print the exact merge-patch body and change nothing.

.EXAMPLE
    ./Enable-M365PublicEndpoint.ps1 -AgentName contoso-support-agent `
        -ProjectEndpoint https://aiservicesktdp.services.ai.azure.com/api/projects/projectktdp

.EXAMPLE
    ./Enable-M365PublicEndpoint.ps1 -AgentName contoso-support-agent `
        -ProjectEndpoint https://... -AuthorizationScheme BotServiceTenant
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$AgentName,

    [string]$ProjectEndpoint,
    [string]$FoundryHost,
    [string]$ProjectName,

    [ValidateSet('BotServiceRbac', 'BotServiceTenant')]
    [string]$AuthorizationScheme = 'BotServiceRbac',

    [switch]$Disable,
    [switch]$WhatIf
)

$ErrorActionPreference = 'Stop'
$AI_RESOURCE = 'https://ai.azure.com'

Import-Module (Join-Path $PSScriptRoot 'M365AgentEndpoint.psm1') -Force

function Write-Info([string]$m) { Write-Host $m -ForegroundColor Cyan }
function Write-OK([string]$m) { Write-Host "    [OK] $m" -ForegroundColor Green }
function Write-Bad([string]$m) { Write-Host "    [FAIL] $m" -ForegroundColor Red }

if (-not $ProjectEndpoint) {
    if (-not $FoundryHost -or -not $ProjectName) {
        throw 'Provide -ProjectEndpoint, or both -FoundryHost and -ProjectName.'
    }
    $ProjectEndpoint = "$($FoundryHost.TrimEnd('/'))/api/projects/$ProjectName"
}
$ProjectEndpoint = $ProjectEndpoint.TrimEnd('/')
$agentUrl = "$ProjectEndpoint/agents/$AgentName`?api-version=v1"

function Get-Agent {
    # The Foundry data-plane firewall can transiently return 403 even for an allowed client.
    for ($attempt = 1; $attempt -le 12; $attempt++) {
        $raw = az rest --method GET --url $agentUrl --resource $AI_RESOURCE -o json 2>&1
        if ($LASTEXITCODE -eq 0) { return ($raw | ConvertFrom-Json) }
        if ("$raw" -match '403|Virtual Network/Firewall') {
            Write-Host "    [retry $attempt/12] firewall denied; waiting..." -ForegroundColor DarkGray
            Start-Sleep -Seconds 5
            continue
        }
        throw "Failed to read agent '$AgentName'.`n$raw"
    }
    throw "Failed to read agent '$AgentName' after 12 attempts (firewall never allowed the request)."
}

Write-Info "==> Reading agent '$AgentName'"
$agent = Get-Agent
$beforeProtocols = @($agent.agent_endpoint.protocol_configuration.PSObject.Properties.Name)
$beforeSchemes = @($agent.agent_endpoint.authorization_schemes | ForEach-Object { $_.type })
$beforeFlag = $agent.agent_endpoint.protocol_configuration.activity.enable_m365_public_endpoint
Write-OK "protocols: $($beforeProtocols -join ', ') | auth: $($beforeSchemes -join ', ') | enable_m365_public_endpoint: $(if ($null -eq $beforeFlag) { '<unset>' } else { $beforeFlag })"

$desired = -not $Disable
$patch = New-AgentEndpointPatch `
    -ProtocolConfiguration $agent.agent_endpoint.protocol_configuration `
    -AuthorizationSchemes $agent.agent_endpoint.authorization_schemes `
    -AuthorizationScheme $AuthorizationScheme `
    -EnableM365PublicEndpoint $desired
$body = ConvertTo-MergePatchJson $patch

Write-Host ''
Write-Host '  Merge-patch body:' -ForegroundColor White
Write-Host $body
Write-Host ''

if ($WhatIf) {
    Write-Host '(WhatIf) Agent not modified.' -ForegroundColor Yellow
    return
}

Write-Info "==> Patching agent endpoint (enable_m365_public_endpoint = $desired)"
$tmp = New-TemporaryFile
try {
    # az rest rejects a UTF-8 BOM.
    [System.IO.File]::WriteAllText($tmp.FullName, $body, (New-Object System.Text.UTF8Encoding($false)))
    $raw = az rest --method PATCH --url $agentUrl --resource $AI_RESOURCE `
        --headers 'Content-Type=application/merge-patch+json' `
        --body "@$($tmp.FullName)" -o json 2>&1
    if ($LASTEXITCODE -ne 0) { throw "PATCH failed.`n$raw" }
}
finally {
    Remove-Item $tmp.FullName -ErrorAction SilentlyContinue
}
Write-OK 'PATCH accepted'

Write-Info '==> Verifying'
$after = Get-Agent
$afterProtocols = @($after.agent_endpoint.protocol_configuration.PSObject.Properties.Name)
$afterSchemes = @($after.agent_endpoint.authorization_schemes | ForEach-Object { $_.type })
$afterFlag = $after.agent_endpoint.protocol_configuration.activity.enable_m365_public_endpoint

$failed = $false

$dropped = @($beforeProtocols | Where-Object { $_ -and $afterProtocols -notcontains $_ })
if ($dropped.Count -gt 0) { Write-Bad "protocols dropped: $($dropped -join ', ')"; $failed = $true }
else { Write-OK "protocols preserved: $($afterProtocols -join ', ')" }

if ($afterProtocols -notcontains 'activity') { Write-Bad 'activity protocol missing'; $failed = $true }

if ($afterFlag -ne $desired) { Write-Bad "enable_m365_public_endpoint is '$afterFlag', expected '$desired'"; $failed = $true }
else { Write-OK "enable_m365_public_endpoint = $afterFlag" }

if ($afterSchemes -notcontains $AuthorizationScheme) { Write-Bad "authorization scheme '$AuthorizationScheme' missing"; $failed = $true }
else { Write-OK "authorization schemes: $($afterSchemes -join ', ')" }

$droppedSchemes = @($beforeSchemes | Where-Object { $_ -and $afterSchemes -notcontains $_ -and $_ -notlike 'BotService*' })
if ($droppedSchemes.Count -gt 0) { Write-Bad "authorization schemes dropped: $($droppedSchemes -join ', ')"; $failed = $true }

Write-Host ''
if ($failed) {
    Write-Host '===== verification FAILED =====' -ForegroundColor Red
    exit 1
}
Write-Host '===== done =====' -ForegroundColor Green
Write-Host 'The Activity Protocol route now accepts Microsoft 365 / Teams source IPs.'
Write-Host 'Publish with scripts/Publish-AgentToTeams.ps1 -UseM365PublicEndpoint (no APIM bridge needed).'
