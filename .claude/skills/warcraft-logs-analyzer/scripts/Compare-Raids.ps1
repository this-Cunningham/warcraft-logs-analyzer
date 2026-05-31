# Compare-Raids.ps1 — ONE deterministic command: two report URLs in, a tabbed
# deep-dive comparison report out. No manual params, no LLM in the generation path.
#
#   .\Compare-Raids.ps1 -OursUrl https://fresh.warcraftlogs.com/reports/AAAA `
#                       -TheirsUrl https://fresh.warcraftlogs.com/reports/BBBB
#
# Auto-resolves report codes, auto-computes the shared bosses (encounter-ID
# intersection), fetches parses + heavy tables for those bosses, builds the
# report, and opens it. Titles/zone default to the reports' own metadata.
#
# Optional: -OursName / -TheirsName to override labels, -OutFile to set the path,
#           -NoOpen to skip launching the browser.

[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$OursUrl,
    [Parameter(Mandatory)][string]$TheirsUrl,
    [string]$OursName,
    [string]$TheirsName,
    [string]$OutFile,
    [switch]$NoOpen
)
$ErrorActionPreference = 'Stop'
$scripts = $PSScriptRoot
. (Join-Path $scripts 'lib.ps1')

function Get-Code($u) {
    if ($u -match 'reports/([^/?#\s]+)') { return $Matches[1] }
    return $u.Trim()    # already a bare code
}
$oursCode = Get-Code $OursUrl
$theirsCode = Get-Code $TheirsUrl

# 1) Lightweight metadata: title, zone, kill encounter IDs (to compute shared bosses).
$metaQ = 'query M($code:String!){reportData{report(code:$code){title zone{name} fights(killType:Kills){encounterID}}}}'
function Get-Meta($code) {
    $r = (Invoke-WclQuery -Query $metaQ -Variables @{ code = $code }).reportData.report
    if (-not $r) { throw "Report '$code' not found or not public." }
    [pscustomobject]@{ title = $r.title; zone = $r.zone.name
        encounters = @($r.fights | ForEach-Object { [int]$_.encounterID } | Where-Object { $_ -ne 0 } | Sort-Object -Unique) }
}
Write-Host "Resolving reports ($oursCode, $theirsCode)..."
$oursMeta = Get-Meta $oursCode
$theirsMeta = Get-Meta $theirsCode

# 2) Shared bosses = encounter-ID intersection (fully deterministic).
$shared = @($oursMeta.encounters | Where-Object { $theirsMeta.encounters -contains $_ })
if (-not $shared.Count) { throw "No shared boss encounters between the two reports." }
Write-Host "Shared bosses ($($shared.Count)): $($shared -join ', ')"

if (-not $OursName) { $OursName = $oursMeta.title }
if (-not $TheirsName) { $TheirsName = $theirsMeta.title }
$zone = $oursMeta.zone

# 3) Paths under <repo>/data and <repo>/reports.
$root = Find-RepoRoot
$dataRoot = Join-Path $root 'data'
if (-not (Test-Path $dataRoot)) { New-Item -ItemType Directory -Force -Path $dataRoot | Out-Null }
$oursDir = Join-Path $dataRoot $oursCode
$theirsDir = Join-Path $dataRoot $theirsCode
$oursParses = Join-Path $dataRoot "$oursCode-parses.json"
$theirsParses = Join-Path $dataRoot "$theirsCode-parses.json"
if (-not $OutFile) { $OutFile = Join-Path $root "reports\$oursCode-vs-$theirsCode.html" }

# 4) Parses (per-player percentile rankings).
$parseQ = 'query P($code:String!){reportData{report(code:$code){rankings(compare:Parses)}}}'
Write-Host "Fetching parses..."
(Invoke-WclQuery -Query $parseQ -Variables @{ code = $oursCode })   | ConvertTo-Json -Depth 40 | Set-Content -Path $oursParses   -Encoding utf8
(Invoke-WclQuery -Query $parseQ -Variables @{ code = $theirsCode }) | ConvertTo-Json -Depth 40 | Set-Content -Path $theirsParses -Encoding utf8

# 5) Deep data (heavy output tables only for the shared bosses).
Write-Host "Fetching deep data (ours)..."
& (Join-Path $scripts 'fetch-report.ps1') -Code $oursCode   -OutDir $oursDir   -FullEncounters $shared
Write-Host "Fetching deep data (theirs)..."
& (Join-Path $scripts 'fetch-report.ps1') -Code $theirsCode -OutDir $theirsDir -FullEncounters $shared

# 6) Build the report (pure PowerShell + static template — deterministic).
Write-Host "Building report..."
& (Join-Path $scripts 'build-deepdive.ps1') -OursDir $oursDir -TheirsDir $theirsDir `
    -OursParses $oursParses -TheirsParses $theirsParses `
    -OursName $OursName -TheirsName $TheirsName -ZoneName $zone -OutFile $OutFile

Write-Host "`n$OursName  vs  $TheirsName  --  $($shared.Count) shared bosses"
Write-Host "Report: $OutFile"
if (-not $NoOpen) { Invoke-Item $OutFile }
