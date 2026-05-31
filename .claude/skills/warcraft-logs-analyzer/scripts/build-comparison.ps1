# build-comparison.ps1 — turn two `rankings(compare: Parses)` JSON dumps into a
# self-contained HTML comparison report.
#
# Each input file is the saved output of:
#   query.ps1 -Query 'query P($code:String!){reportData{report(code:$code){rankings(compare:Parses)}}}' -Variables '{"code":"..."}'
#
# Usage:
#   .\build-comparison.ps1 -OursFile .\data\ours-parses.json -TheirsFile .\data\demo-parses.json `
#       -OursName "Our Raid" -TheirsName "Tuesday Split" -ZoneName "SSC / TK" `
#       -OutFile .\reports\ssc-comparison.html

param(
    [Parameter(Mandatory)][string]$OursFile,
    [Parameter(Mandatory)][string]$TheirsFile,
    [string]$OursName   = 'Our Raid',
    [string]$TheirsName = 'Benchmark',
    [string]$ZoneName   = '',
    [Parameter(Mandatory)][string]$OutFile
)

$ErrorActionPreference = 'Stop'

function Get-Fights($path) {
    $j = Get-Content -Raw -Path $path | ConvertFrom-Json
    return $j.reportData.report.rankings.data
}

function Get-Players($fight) {
    $roleLabel = @{ tanks = 'tank'; healers = 'healer'; dps = 'dps' }
    $players = @()
    foreach ($roleName in 'tanks', 'healers', 'dps') {
        $role = $fight.roles.$roleName
        if ($null -eq $role) { continue }
        foreach ($c in $role.characters) {
            $players += [pscustomobject]@{
                name   = $c.name
                class  = $c.class
                spec   = $c.spec
                role   = $roleLabel[$roleName]
                parse  = [int]$c.rankPercent
                amount = [math]::Round([double]$c.amount, 1)
            }
        }
    }
    return $players
}

function Index-ByEncounter($fights) {
    $map = @{}
    foreach ($f in $fights) {
        $players = Get-Players $f
        $parses = ($players | Where-Object { $_.parse -ge 0 } | ForEach-Object { $_.parse })
        $avg = if ($parses.Count) { [math]::Round(($parses | Measure-Object -Average).Average, 1) } else { 0 }
        $map[[string]$f.encounter.id] = [pscustomobject]@{
            name       = $f.encounter.name
            durationMs = [long]$f.duration
            deaths     = [int]$f.deaths
            avgParse   = $avg
            players    = $players
        }
    }
    return $map
}

$ours   = Index-ByEncounter (Get-Fights $OursFile)
$theirs = Index-ByEncounter (Get-Fights $TheirsFile)

# Common encounters, ordered by our kill order in the file.
$commonIds = $ours.Keys | Where-Object { $theirs.ContainsKey($_) }

$bosses = @()
foreach ($id in $commonIds) {
    $bosses += [pscustomobject]@{
        encounterID = [int]$id
        name        = $ours[$id].name
        ours        = $ours[$id]
        theirs      = $theirs[$id]
    }
}

function Avg($vals) { if ($vals.Count) { [math]::Round(($vals | Measure-Object -Average).Average, 1) } else { 0 } }
function Sum($vals) { ($vals | Measure-Object -Sum).Sum }

$summary = [pscustomobject]@{
    bossCount      = $bosses.Count
    oursAvgParse   = Avg ($bosses | ForEach-Object { $_.ours.avgParse })
    theirsAvgParse = Avg ($bosses | ForEach-Object { $_.theirs.avgParse })
    oursDeaths     = Sum ($bosses | ForEach-Object { $_.ours.deaths })
    theirsDeaths   = Sum ($bosses | ForEach-Object { $_.theirs.deaths })
    oursDurationMs   = Sum ($bosses | ForEach-Object { $_.ours.durationMs })
    theirsDurationMs = Sum ($bosses | ForEach-Object { $_.theirs.durationMs })
}

$payload = [pscustomobject]@{
    zone    = $ZoneName
    ours    = @{ title = $OursName }
    theirs  = @{ title = $TheirsName }
    summary = $summary
    bosses  = $bosses
}

$json = $payload | ConvertTo-Json -Depth 30 -Compress

$tplPath = Join-Path $PSScriptRoot '..\templates\report.html'
# Read/write as UTF-8 explicitly — PS 5.1's Get-Content/Set-Content mangle
# multibyte chars (·, −, accented player names) on no-BOM files.
$utf8 = New-Object System.Text.UTF8Encoding($false)   # no BOM
$tpl = [System.IO.File]::ReadAllText($tplPath, [System.Text.Encoding]::UTF8)
$html = $tpl.Replace('/*__DATA__*/null', $json)

$outFull = if ([System.IO.Path]::IsPathRooted($OutFile)) { $OutFile } else { [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $OutFile)) }
$outDir = Split-Path -Parent $outFull
if ($outDir -and -not (Test-Path $outDir)) { New-Item -ItemType Directory -Force -Path $outDir | Out-Null }
[System.IO.File]::WriteAllText($outFull, $html, $utf8)

Write-Output "Report written to $OutFile ($($bosses.Count) common bosses)"
