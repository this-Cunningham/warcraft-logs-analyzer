# fetch-report.ps1 — pull everything the deep-dive needs for ONE report into a
# per-report folder. Run once per report, then feed both folders to build-deepdive.ps1.
#
#   .\fetch-report.ps1 -Code 1GHrpaNc2YM4hKTJ -OutDir .\data\demo
#
# Writes:
#   <OutDir>\fights.json          (boss kills: id, name, encounterID, start/end, size, ilvl)
#   <OutDir>\playerdetails.json   (combatantInfo: gear/enchants/gems, potionUse)
#   <OutDir>\boss-<encounterID>.json  (per-kill: buffs + boss debuffs, in one call)

param(
    [Parameter(Mandatory)][string]$Code,
    [Parameter(Mandatory)][string]$OutDir,
    # Encounter IDs that should also pull the heavy output tables (DamageDone,
    # Healing, DamageTaken, Interrupts, Dispels). Usually the shared bosses only,
    # since those responses are large. Others get just buffs/debuffs.
    [int[]]$FullEncounters = @()
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'lib.ps1')

if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Force -Path $OutDir | Out-Null }
function Save($obj, $name) {
    $p = Join-Path $OutDir $name
    $obj | ConvertTo-Json -Depth 40 | Set-Content -Path $p -Encoding utf8
}

# 1) Boss kills (phaseTransitions ride along here — cheap, used by the Phases view)
$killsQ = 'query K($code:String!){reportData{report(code:$code){title fights(killType:Kills){id name encounterID difficulty startTime endTime size averageItemLevel phaseTransitions{id startTime}}}}}'
$kills = (Invoke-WclQuery -Query $killsQ -Variables @{ code = $Code })
Save $kills 'fights.json'
$fights = $kills.reportData.report.fights
$fightIDs = @($fights | ForEach-Object { [int]$_.id })
Write-Host "[$Code] $($fights.Count) boss kills"

# 2) Player details (gear/enchants/gems/potions) across all kills — gear is static,
#    one call covers the roster.
$pdQ = 'query D($code:String!,$f:[Int]!){reportData{report(code:$code){playerDetails(fightIDs:$f, includeCombatantInfo:true)}}}'
$pd = Invoke-WclQuery -Query $pdQ -Variables @{ code = $Code; f = $fightIDs }
Save $pd 'playerdetails.json'
Write-Host "[$Code] player details saved"

# 3) Per-boss tables (one call per boss via aliases). Shared bosses also pull the
#    heavy output tables for the Dive Deeper modules.
$liteQ = 'query F($code:String!,$f:[Int]!){reportData{report(code:$code){buffs: table(dataType:Buffs, fightIDs:$f) debuffs: table(dataType:Debuffs, fightIDs:$f, hostilityType:Enemies)}}}'
$fullQ = 'query F($code:String!,$f:[Int]!){reportData{report(code:$code){buffs: table(dataType:Buffs, fightIDs:$f) debuffs: table(dataType:Debuffs, fightIDs:$f, hostilityType:Enemies) dd: table(dataType:DamageDone, fightIDs:$f) heal: table(dataType:Healing, fightIDs:$f) dt: table(dataType:DamageTaken, fightIDs:$f) intr: table(dataType:Interrupts, fightIDs:$f) disp: table(dataType:Dispels, fightIDs:$f) deaths: table(dataType:Deaths, fightIDs:$f)}}}'
foreach ($fight in $fights) {
    $fid = [int]$fight.id
    $enc = [int]$fight.encounterID
    $heavy = $FullEncounters -contains $enc
    $res = Invoke-WclQuery -Query ($(if ($heavy) { $fullQ } else { $liteQ })) -Variables @{ code = $Code; f = @($fid) }
    Save $res ("boss-$enc.json")
    Write-Host "[$Code]   $(if($heavy){'FULL'}else{'lite'}): $($fight.name) (enc $enc)"
}

Write-Host "[$Code] done -> $OutDir"
