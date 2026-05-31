# query.ps1 — run a GraphQL query against the WCL public API and print JSON.
#
# Usage:
#   .\query.ps1 -QueryFile .\queries\report-summary.graphql -Variables '{"code":"abc123"}'
#   .\query.ps1 -Query 'query { rateLimitData { limitPerHour pointsSpentThisHour } }'
#
# Output is JSON on stdout (depth 30), suitable for piping or capturing.

[CmdletBinding(DefaultParameterSetName = 'Inline')]
param(
    [Parameter(Mandatory, ParameterSetName = 'Inline')][string]$Query,
    [Parameter(Mandatory, ParameterSetName = 'File')][string]$QueryFile,
    [string]$Variables,            # JSON object string, e.g. '{"code":"abc","fightIDs":[1,2]}'
    [string]$OutFile               # optional: also write JSON to this path
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'lib.ps1')

if ($PSCmdlet.ParameterSetName -eq 'File') {
    $Query = Get-Content -Raw -Path $QueryFile
}

$vars = $null
if ($Variables) {
    # Convert the JSON string into a hashtable for ConvertTo-Json round-tripping.
    $obj = $Variables | ConvertFrom-Json
    $vars = @{}
    foreach ($p in $obj.PSObject.Properties) { $vars[$p.Name] = $p.Value }
}

$data = Invoke-WclQuery -Query $Query -Variables $vars
$json = $data | ConvertTo-Json -Depth 30

if ($OutFile) { $json | Set-Content -Path $OutFile -Encoding utf8 }
Write-Output $json
