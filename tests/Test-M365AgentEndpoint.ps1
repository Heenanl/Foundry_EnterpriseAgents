<#
    Offline regression checks for the Microsoft 365 public-endpoint merge patch.

    The PATCH replaces `protocol_configuration` and `authorization_schemes` wholesale,
    so these tests pin the preservation behaviour that stops a publish from silently
    dropping protocols the endpoint still needs.

    Run: pwsh tests/Test-M365AgentEndpoint.ps1
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Import-Module (Join-Path $PSScriptRoot '../scripts/M365AgentEndpoint.psm1') -Force

$script:Failures = 0
$script:Passed = 0

function Assert-That {
    param([bool]$Condition, [string]$Message)
    if ($Condition) {
        $script:Passed++
        Write-Host "  ok   $Message" -ForegroundColor DarkGray
    }
    else {
        $script:Failures++
        Write-Host "  FAIL $Message" -ForegroundColor Red
    }
}

function New-AgentEndpoint([string]$Json) { ($Json | ConvertFrom-Json).agent_endpoint }

Write-Host 'enable_m365_public_endpoint patch builder' -ForegroundColor Cyan

# A realistic already-published agent: activity + responses, Entra + BotServiceRbac.
$published = New-AgentEndpoint @'
{
  "agent_endpoint": {
    "protocol_configuration": { "activity": {}, "responses": {} },
    "authorization_schemes": [ { "type": "Entra" }, { "type": "BotServiceRbac" } ]
  }
}
'@

$patch = New-AgentEndpointPatch -ProtocolConfiguration $published.protocol_configuration -AuthorizationSchemes $published.authorization_schemes
$protocols = $patch.agent_endpoint.protocol_configuration
$schemeTypes = @($patch.agent_endpoint.authorization_schemes | ForEach-Object { $_['type'] })

Assert-That ($protocols.ContainsKey('responses')) 'keeps responses on a published agent'
Assert-That ($protocols.ContainsKey('activity')) 'keeps activity on a published agent'
Assert-That ($protocols['activity']['enable_m365_public_endpoint'] -eq $true) 'sets the flag to true'
Assert-That ($schemeTypes -contains 'Entra') 'keeps Entra'
Assert-That ($schemeTypes -contains 'BotServiceRbac') 'keeps BotServiceRbac'
Assert-That ($schemeTypes.Count -eq 2) 'does not duplicate schemes'

# The documented footgun: protocols omitted from the PATCH are dropped.
$multiProtocol = New-AgentEndpoint @'
{
  "agent_endpoint": {
    "protocol_configuration": {
      "responses": {},
      "invocations": {},
      "a2a": { "version": "1.0" },
      "mcp": {}
    },
    "authorization_schemes": [ { "type": "Entra" } ]
  }
}
'@

$patch = New-AgentEndpointPatch -ProtocolConfiguration $multiProtocol.protocol_configuration -AuthorizationSchemes $multiProtocol.authorization_schemes
$protocols = $patch.agent_endpoint.protocol_configuration
$schemeTypes = @($patch.agent_endpoint.authorization_schemes | ForEach-Object { $_['type'] })

foreach ($name in @('responses', 'invocations', 'a2a', 'mcp')) {
    Assert-That ($protocols.ContainsKey($name)) "preserves the $name protocol"
}
Assert-That ($protocols['a2a']['version'] -eq '1.0') 'preserves nested protocol settings'
Assert-That ($protocols.ContainsKey('activity')) 'adds activity when the agent has none'
Assert-That ($protocols['activity']['enable_m365_public_endpoint'] -eq $true) 'enables the flag on the added activity protocol'
Assert-That ($schemeTypes -contains 'Entra') 'keeps Entra when adding a Bot Service scheme'
Assert-That ($schemeTypes -contains 'BotServiceRbac') 'adds the requested Bot Service scheme'

# Publishing replaces a different Bot Service scheme rather than stacking both.
$tenantScoped = New-AgentEndpoint @'
{
  "agent_endpoint": {
    "protocol_configuration": { "activity": {}, "responses": {} },
    "authorization_schemes": [ { "type": "Entra" }, { "type": "BotServiceTenant" } ]
  }
}
'@

$patch = New-AgentEndpointPatch -ProtocolConfiguration $tenantScoped.protocol_configuration -AuthorizationSchemes $tenantScoped.authorization_schemes -AuthorizationScheme 'BotServiceRbac'
$schemeTypes = @($patch.agent_endpoint.authorization_schemes | ForEach-Object { $_['type'] })

Assert-That ($schemeTypes -contains 'BotServiceRbac') 'switches to the requested Bot Service scheme'
Assert-That ($schemeTypes -notcontains 'BotServiceTenant') 'removes the superseded Bot Service scheme'
Assert-That ($schemeTypes -contains 'Entra') 'still keeps Entra when switching schemes'

# Preserve existing activity settings instead of replacing the object.
$activityWithSettings = New-AgentEndpoint @'
{
  "agent_endpoint": {
    "protocol_configuration": { "activity": { "some_existing_setting": "keep-me" } },
    "authorization_schemes": []
  }
}
'@

$patch = New-AgentEndpointPatch -ProtocolConfiguration $activityWithSettings.protocol_configuration -AuthorizationSchemes $activityWithSettings.authorization_schemes
Assert-That ($patch.agent_endpoint.protocol_configuration['activity']['some_existing_setting'] -eq 'keep-me') 'preserves existing activity settings'

# Rollback path.
$patch = New-AgentEndpointPatch -ProtocolConfiguration $published.protocol_configuration -AuthorizationSchemes $published.authorization_schemes -EnableM365PublicEndpoint $false
Assert-That ($patch.agent_endpoint.protocol_configuration['activity']['enable_m365_public_endpoint'] -eq $false) 'can roll the flag back to false'

# Rollback must not re-scope a tenant-published agent: omitting -AuthorizationScheme keeps
# whatever Bot Service scheme the endpoint already has.
$patch = New-AgentEndpointPatch -ProtocolConfiguration $tenantScoped.protocol_configuration -AuthorizationSchemes $tenantScoped.authorization_schemes -EnableM365PublicEndpoint $false
$schemeTypes = @($patch.agent_endpoint.authorization_schemes | ForEach-Object { $_['type'] })
Assert-That ($schemeTypes -contains 'BotServiceTenant') 'rollback keeps BotServiceTenant when no scheme is requested'
Assert-That ($schemeTypes -notcontains 'BotServiceRbac') 'rollback does not silently downgrade to BotServiceRbac'

$patch = New-AgentEndpointPatch -ProtocolConfiguration $tenantScoped.protocol_configuration -AuthorizationSchemes $tenantScoped.authorization_schemes
$schemeTypes = @($patch.agent_endpoint.authorization_schemes | ForEach-Object { $_['type'] })
Assert-That ($schemeTypes -contains 'BotServiceTenant') 'enable keeps an existing BotServiceTenant scheme'

# A brand-new agent with no endpoint configuration at all.
$patch = New-AgentEndpointPatch -ProtocolConfiguration $null -AuthorizationSchemes $null
$schemeTypes = @($patch.agent_endpoint.authorization_schemes | ForEach-Object { $_['type'] })
Assert-That ($patch.agent_endpoint.protocol_configuration['activity']['enable_m365_public_endpoint'] -eq $true) 'handles an agent with no protocol configuration'
Assert-That ($schemeTypes -contains 'BotServiceRbac') 'adds a Bot Service scheme when none exist'

# Serialization must match Content-Type: application/merge-patch+json expectations.
$json = ConvertTo-MergePatchJson (New-AgentEndpointPatch -ProtocolConfiguration $published.protocol_configuration -AuthorizationSchemes $published.authorization_schemes)
$round = $json | ConvertFrom-Json
Assert-That ($round.agent_endpoint.protocol_configuration.activity.enable_m365_public_endpoint -eq $true) 'serializes the flag'
Assert-That ($round.agent_endpoint.protocol_configuration.responses -ne $null) 'serializes an empty protocol as an object'
Assert-That (@($round.agent_endpoint.authorization_schemes).Count -eq 2) 'serializes authorization schemes as an array'

Write-Host ''
if ($script:Failures -gt 0) {
    Write-Host "FAILED  $($script:Failures) failed, $($script:Passed) passed" -ForegroundColor Red
    exit 1
}
Write-Host "OK      $($script:Passed) passed" -ForegroundColor Green
