[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$AppId,

  [string]$OutputPath = (Join-Path $PSScriptRoot "appPackage.zip")
)

$ErrorActionPreference = "Stop"

if ($AppId -notmatch '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$') {
  throw "AppId must be a GUID."
}

$stagingDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $stagingDirectory | Out-Null

try {
  $manifest = Get-Content (Join-Path $PSScriptRoot "manifest.template.json") -Raw
  $manifest.Replace("{{APP_ID}}", $AppId) | Set-Content (Join-Path $stagingDirectory "manifest.json") -Encoding utf8NoBOM
  Copy-Item (Join-Path $PSScriptRoot "default-color-icon.png") $stagingDirectory
  Copy-Item (Join-Path $PSScriptRoot "default-outline-icon.png") $stagingDirectory
  Compress-Archive -Path (Join-Path $stagingDirectory "*") -DestinationPath $OutputPath -Force
} finally {
  Remove-Item $stagingDirectory -Recurse -Force
}
