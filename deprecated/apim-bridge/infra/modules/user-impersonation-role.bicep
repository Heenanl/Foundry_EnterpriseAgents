// =============================================================================
//  user-impersonation-role.bicep
//  Creates the custom role that lets a TRUSTED MIDDLE TIER (e.g. the APIM bridge
//  managed identity, or a Teams bot's identity) send the `x-ms-user-identity`
//  header to a Foundry hosted agent, so the platform isolates hosted-agent
//  sessions per end user.
//
//  Why a custom role: the data action
//    Microsoft.CognitiveServices/accounts/AIServices/agents/endpoints/UserIdentityImpersonation/action
//  is NOT included in any built-in role (it used to be covered by the
//  Microsoft.CognitiveServices/* data action, which no longer grants it). A
//  caller that sends x-ms-user-identity without this permission gets a 403.
//
//  IMPORTANT SCOPE OF THIS PERMISSION (per Microsoft docs + the Brandon Litton
//  Microsoft Q&A, learn.microsoft.com/answers/a/12912519):
//    - x-ms-user-identity = per-user SESSION ISOLATION only. It is NOT an OAuth
//      credential selector: it does NOT, on its own, cause a Toolbox/MCP to
//      receive a per-user access token. Per-user DATA access still requires a
//      per-user token passed to the MCP (e.g. our x-client-user-token gateway),
//      with the MCP as the final authorization boundary.
//    - The middle tier ALSO needs interact/action (built-in "Foundry Agent
//      Consumer") to call the agent endpoint at all. Assign that separately.
// =============================================================================

targetScope = 'resourceGroup'

@description('Name of the EXISTING Foundry (Cognitive Services / AIServices) account to scope the role to.')
param foundryAccountName string

@description('Object ID (principal ID) of the trusted middle-tier identity that will send x-ms-user-identity (e.g. the APIM system-assigned MI principalId).')
param middleTierPrincipalId string

@description('Principal type of middleTierPrincipalId.')
@allowed([
  'ServicePrincipal'
  'User'
  'Group'
])
param principalType string = 'ServicePrincipal'

@description('Display name for the custom role definition.')
param roleName string = 'Foundry Agent User Identity Impersonation'

resource foundry 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: foundryAccountName
}

// Deterministic role definition GUID (stable across redeploys for this account).
var roleDefName = guid(foundry.id, 'user-identity-impersonation-role')

resource impersonationRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' = {
  name: roleDefName
  properties: {
    roleName: '${roleName} (${foundryAccountName})'
    description: 'Allows a trusted middle tier to send x-ms-user-identity to isolate hosted-agent sessions per end user. No general Foundry access.'
    type: 'CustomRole'
    assignableScopes: [
      foundry.id
    ]
    permissions: [
      {
        actions: []
        notActions: []
        dataActions: [
          'Microsoft.CognitiveServices/accounts/AIServices/agents/endpoints/UserIdentityImpersonation/action'
        ]
        notDataActions: []
      }
    ]
  }
}

resource impersonationAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, middleTierPrincipalId, roleDefName)
  scope: foundry
  properties: {
    roleDefinitionId: impersonationRole.id
    principalId: middleTierPrincipalId
    principalType: principalType
  }
}

@description('Resource ID of the created custom role definition.')
output roleDefinitionId string = impersonationRole.id
