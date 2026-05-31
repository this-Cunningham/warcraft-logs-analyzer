# build-deepdive.ps1 — tabbed (Overview + Dive Deeper) raid comparison report.
# Consumes the folders produced by fetch-report.ps1 plus the two parse files.
#
#   .\build-deepdive.ps1 -OursDir .\data\ours -TheirsDir .\data\demo `
#       -OursParses .\data\ours-parses.json -TheirsParses .\data\demo-parses.json `
#       -OursName "Our Raid" -TheirsName "Benchmark" -ZoneName "SSC / TK" `
#       -OutFile .\reports\deepdive.html

param(
    [Parameter(Mandatory)][string]$OursDir,
    [Parameter(Mandatory)][string]$TheirsDir,
    [Parameter(Mandatory)][string]$OursParses,
    [Parameter(Mandatory)][string]$TheirsParses,
    [string]$OursName   = 'Our Raid',
    [string]$TheirsName = 'Benchmark',
    [string]$ZoneName   = '',
    [Parameter(Mandatory)][string]$OutFile
)
$ErrorActionPreference = 'Stop'

function ReadJson($p) { Get-Content -Raw -Path $p | ConvertFrom-Json }

# ---------- OVERVIEW (from parse rankings) ----------
function Get-Fights($path) { (ReadJson $path).reportData.report.rankings.data }
function Get-Players($fight) {
    $roleLabel = @{ tanks = 'tank'; healers = 'healer'; dps = 'dps' }
    $players = @()
    foreach ($rn in 'tanks', 'healers', 'dps') {
        $role = $fight.roles.$rn
        if ($null -eq $role) { continue }
        foreach ($c in $role.characters) {
            $players += [pscustomobject]@{ name = $c.name; class = $c.class; spec = $c.spec
                role = $roleLabel[$rn]; parse = [int]$c.rankPercent; amount = [math]::Round([double]$c.amount, 1) }
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
        $map[[string]$f.encounter.id] = [pscustomobject]@{ name = $f.encounter.name
            durationMs = [long]$f.duration; deaths = [int]$f.deaths; avgParse = $avg; players = $players }
    }
    return $map
}
function Avg($v) { if ($v.Count) { [math]::Round(($v | Measure-Object -Average).Average, 1) } else { 0 } }
function Sum($v) { [int](($v | Measure-Object -Sum).Sum) }

$oursIdx   = Index-ByEncounter (Get-Fights $OursParses)
$theirsIdx = Index-ByEncounter (Get-Fights $TheirsParses)
$commonIds = $oursIdx.Keys | Where-Object { $theirsIdx.ContainsKey($_) }

$bosses = @()
foreach ($id in $commonIds) {
    $bosses += [pscustomobject]@{ encounterID = [int]$id; name = $oursIdx[$id].name
        ours = $oursIdx[$id]; theirs = $theirsIdx[$id] }
}
$summary = [pscustomobject]@{
    bossCount = $bosses.Count
    oursAvgParse   = Avg ($bosses | ForEach-Object { $_.ours.avgParse });   theirsAvgParse = Avg ($bosses | ForEach-Object { $_.theirs.avgParse })
    oursDeaths     = Sum ($bosses | ForEach-Object { $_.ours.deaths });     theirsDeaths   = Sum ($bosses | ForEach-Object { $_.theirs.deaths })
    oursDurationMs = Sum ($bosses | ForEach-Object { $_.ours.durationMs }); theirsDurationMs = Sum ($bosses | ForEach-Object { $_.theirs.durationMs })
}

# ---------- COMPOSITION (distinct roster from parses) ----------
# Roster restricted to the given encounters (the shared bosses) so the composition
# comparison is apples-to-apples and excludes players who only showed up elsewhere.
function Get-Roster($idx, $encIds) {
    $byName = @{}
    foreach ($enc in @($encIds)) {
        if (-not $idx.ContainsKey($enc)) { continue }
        foreach ($p in $idx[$enc].players) {
            if (-not $byName.ContainsKey($p.name)) {
                $byName[$p.name] = [pscustomobject]@{ name = $p.name; class = $p.class; spec = $p.spec; role = $p.role }
            }
        }
    }
    return $byName.Values
}
$oursRoster   = @(Get-Roster $oursIdx @($commonIds))
$theirsRoster = @(Get-Roster $theirsIdx @($commonIds))
$oursSpec = @{}; foreach ($p in $oursRoster) { $oursSpec[$p.name] = $p.spec }
$theirsSpec = @{}; foreach ($p in $theirsRoster) { $theirsSpec[$p.name] = $p.spec }
function NamesByRole($roster, $role) { @($roster | Where-Object { $_.role -eq $role } | ForEach-Object { $_.name }) }
$oursDps = NamesByRole $oursRoster 'dps'; $oursHeal = NamesByRole $oursRoster 'healer'; $oursTank = NamesByRole $oursRoster 'tank'
$theirsDps = NamesByRole $theirsRoster 'dps'; $theirsHeal = NamesByRole $theirsRoster 'healer'; $theirsTank = NamesByRole $theirsRoster 'tank'

function ClassCounts($roster) {
    $byClass = @{}
    foreach ($p in $roster) {
        if (-not $byClass.ContainsKey($p.class)) { $byClass[$p.class] = @{ count = 0; specs = @{} } }
        $byClass[$p.class].count++
        $spec = if ($p.spec) { $p.spec } else { 'Unknown' }
        $byClass[$p.class].specs[$spec] = ([int]$byClass[$p.class].specs[$spec]) + 1
    }
    $out = @()
    foreach ($k in ($byClass.Keys | Sort-Object)) {
        $specs = @()
        foreach ($s in ($byClass[$k].specs.Keys | Sort-Object { - $byClass[$k].specs[$_] })) {
            $specs += [pscustomobject]@{ spec = $s; count = $byClass[$k].specs[$s] }
        }
        $out += [pscustomobject]@{ class = $k; count = $byClass[$k].count; specs = $specs }
    }
    return $out
}
function HasProvider($roster, $class, $spec) {
    foreach ($p in $roster) {
        if ($p.class -eq $class) {
            if (-not $spec) { return $true }
            if ($p.spec -and ($p.spec -like "*$spec*")) { return $true }
        }
    }
    return $false
}
# High-impact TBC raid contributions: class/spec -> buff/debuff + why it matters.
$providerChecks = @(
    @{ buff = 'Misery';                 class = 'Priest';  spec = 'Shadow';      impact = '+3% spell damage taken by boss, plus a mana battery for casters' }
    @{ buff = 'Improved Faerie Fire';   class = 'Druid';   spec = 'Balance';     impact = '+3% spell hit for the whole raid (huge for casters)' }
    @{ buff = 'Ferocious Inspiration';  class = 'Hunter';  spec = 'Beast';       impact = '+3% damage to the raid' }
    @{ buff = 'Trueshot Aura';          class = 'Hunter';  spec = 'Marksmanship';impact = 'Raid-wide attack power' }
    @{ buff = 'Expose Weakness';        class = 'Hunter';  spec = 'Survival';    impact = 'Raid-wide attack power from crits' }
    @{ buff = 'Bloodlust / Heroism';    class = 'Shaman';  spec = '';            impact = '+30% raid haste burst window' }
    @{ buff = 'Windfury Totem';         class = 'Shaman';  spec = 'Enhancement'; impact = 'Big melee damage boost' }
    @{ buff = 'Improved Scorch (fire)'; class = 'Mage';    spec = 'Fire';        impact = '+15% fire damage taken by boss' }
    @{ buff = 'Curse of the Elements';  class = 'Warlock'; spec = '';            impact = '+10% spell damage taken by boss' }
    @{ buff = 'Leader of the Pack';     class = 'Druid';   spec = 'Feral';       impact = '+5% melee/ranged crit for the raid' }
    @{ buff = 'Judgement of Wisdom';    class = 'Paladin'; spec = '';            impact = 'Mana return for the raid' }
    @{ buff = 'Battle Shout';           class = 'Warrior'; spec = '';            impact = 'Raid-wide attack power' }
)
$gaps = @()
foreach ($c in $providerChecks) {
    $o = HasProvider $oursRoster $c.class $c.spec
    $t = HasProvider $theirsRoster $c.class $c.spec
    $gaps += [pscustomobject]@{ buff = $c.buff; ours = $o; theirs = $t; impact = $c.impact }
}
$composition = [pscustomobject]@{
    oursClasses = ClassCounts $oursRoster; theirsClasses = ClassCounts $theirsRoster
    oursSize = $oursRoster.Count; theirsSize = $theirsRoster.Count; gaps = $gaps
}

# ---------- ENCHANT / GEM / CONSUMABLE AUDIT (from playerDetails) ----------
# Core enchantable slots in TBC (exclude rings = enchanter-only, offhand/ranged = conditional).
$enchSlots = @{ 0 = 'Head'; 2 = 'Shoulder'; 4 = 'Chest'; 6 = 'Legs'; 7 = 'Feet'; 8 = 'Wrist'; 9 = 'Hands'; 14 = 'Back'; 15 = 'Weapon' }
function Audit-Report($dir) {
    $pd = (ReadJson (Join-Path $dir 'playerdetails.json')).reportData.report.playerDetails.data.playerDetails
    $players = @()
    foreach ($rn in 'tanks', 'healers', 'dps') {
        foreach ($pl in $pd.$rn) {
            $gear = $pl.combatantInfo.gear
            $missing = @()
            $gems = 0
            $weaponOil = $false
            foreach ($slot in ($enchSlots.Keys | Sort-Object)) {
                $item = $gear | Where-Object { $_.slot -eq $slot } | Select-Object -First 1
                if ($item -and $item.id -ne 0) {
                    if (-not $item.permanentEnchant -or [int]$item.permanentEnchant -eq 0) { $missing += $enchSlots[$slot] }
                    if ($slot -eq 15 -and $item.temporaryEnchant -and [int]$item.temporaryEnchant -ne 0) { $weaponOil = $true }
                }
            }
            foreach ($item in $gear) { if ($item.gems) { $gems += @($item.gems).Count } }
            $roleLbl = @{ tanks = 'tank'; healers = 'healer'; dps = 'dps' }[$rn]
            $players += [pscustomobject]@{ name = $pl.name; class = $pl.type; role = $roleLbl
                missingEnchants = @($missing); missingCount = $missing.Count; gems = $gems
                weaponOil = $weaponOil }
        }
    }
    $totalMissing = Sum ($players | ForEach-Object { $_.missingCount })
    $noOil = @($players | Where-Object { -not $_.weaponOil }).Count
    $fullEnch = @($players | Where-Object { $_.missingCount -eq 0 }).Count
    [pscustomobject]@{ players = $players; totalMissingEnchants = $totalMissing
        playersNoWeaponOil = $noOil; fullyEnchanted = $fullEnch; playerCount = $players.Count
        avgGems = Avg ($players | ForEach-Object { $_.gems }) }
}
$audit = [pscustomobject]@{ ours = (Audit-Report $OursDir); theirs = (Audit-Report $TheirsDir) }

# ---------- PER-BOSS BUFF/DEBUFF UPTIME + LUST TIMING ----------
function Fight-Map($dir) {
    $m = @{}
    foreach ($f in (ReadJson (Join-Path $dir 'fights.json')).reportData.report.fights) {
        $m[[string]$f.encounterID] = [pscustomobject]@{ start = [long]$f.startTime; end = [long]$f.endTime }
    }
    return $m
}
$oursFights   = Fight-Map $OursDir
$theirsFights = Fight-Map $TheirsDir

$keyBuffs   = @('Bloodlust', 'Heroism', 'Battle Shout', 'Blessing of Kings', 'Gift of the Wild', 'Ferocious Inspiration', 'Leader of the Pack', 'Drums of Battle', 'Arcane Brilliance', 'Windfury')
$keyDebuffs = @('Sunder Armor', 'Expose Armor', 'Curse of the Elements', 'Faerie Fire', 'Misery', 'Judgement of Wisdom', 'Judgement of the Crusader', 'Demoralizing Shout')

function UptimePct($auras, $name, $durMs) {
    if ($durMs -le 0) { return $null }
    $a = $auras | Where-Object { $_.name -eq $name } | Select-Object -First 1
    if (-not $a) { return 0 }
    return [math]::Min(100, [math]::Round([double]$a.totalUptime / $durMs * 100, 0))
}
function LustSec($auras, $fightStart) {
    $a = $auras | Where-Object { $_.name -eq 'Bloodlust' -or $_.name -eq 'Heroism' } | Select-Object -First 1
    if (-not $a -or -not $a.bands) { return $null }
    $first = (@($a.bands) | Sort-Object startTime | Select-Object -First 1).startTime
    return [math]::Round(([long]$first - [long]$fightStart) / 1000, 0)
}
function Load-Boss($dir, $enc) {
    $p = Join-Path $dir "boss-$enc.json"
    if (-not (Test-Path $p)) { return $null }
    return (ReadJson $p).reportData.report
}
# --- Dive Deeper output-quality extractors (heavy tables) ---
function ActivityPct($report, $dur, $dpsNames) {
    if (-not $report.dd -or $dur -le 0) { return $null }
    $es = @($report.dd.data.entries | Where-Object { $dpsNames -contains $_.name })
    if (-not $es.Count) { return $null }
    Avg ($es | ForEach-Object { [math]::Min(100, [double]$_.activeTime / $dur * 100) })
}
function OverhealPct($report, $healerNames) {
    if (-not $report.heal) { return $null }
    $vals = @()
    foreach ($e in @($report.heal.data.entries | Where-Object { $healerNames -contains $_.name })) {
        $den = [double]$e.total + [double]$e.overheal
        if ($den -gt 0) { $vals += ([double]$e.overheal / $den * 100) }
    }
    if (-not $vals.Count) { return $null }
    Avg $vals
}
function DmgTakenExTanks($report, $tankNames) {
    if (-not $report.dt) { return $null }
    Sum (@($report.dt.data.entries | Where-Object { $tankNames -notcontains $_.name }) | ForEach-Object { [long]$_.total })
}
# Damage-taken per second — normalizes for kill time so slower fights aren't penalized.
function Dtps($dmg, $durMs) { if ($null -eq $dmg -or $durMs -le 0) { return $null }; [math]::Round([double]$dmg * 1000 / $durMs, 0) }
function AbilityAgg($report, $tankNames) {
    $agg = @{}
    if (-not $report.dt) { return $agg }
    foreach ($e in @($report.dt.data.entries | Where-Object { $tankNames -notcontains $_.name })) {
        foreach ($a in @($e.abilities)) { $agg[$a.name] = ([long]$agg[$a.name]) + [long]$a.total }
    }
    return $agg
}
# Unified per-ability damage-taken comparison: union of both raids' sources so the
# same ability lines up in one row. Top N by the larger of the two sides.
function DmgCompare($oR, $oTank, $tR, $tTank, $n) {
    $oa = AbilityAgg $oR $oTank; $ta = AbilityAgg $tR $tTank
    $names = @(@($oa.Keys) + @($ta.Keys)) | Sort-Object -Unique
    $rows = @()
    foreach ($nm in $names) { $rows += [pscustomobject]@{ name = $nm; ours = [long]$oa[$nm]; theirs = [long]$ta[$nm] } }
    @($rows | Sort-Object { [math]::Max($_.ours, $_.theirs) } -Descending | Select-Object -First $n)
}
# Interrupts/Dispels tables nest as data.entries[0].entries[] (by ability, with details[] per actor).
function CountActions($report, $alias) {
    $tbl = $report.$alias
    if (-not $tbl -or -not $tbl.data.entries) { return 0 }
    $inner = @($tbl.data.entries)[0].entries
    if (-not $inner) { return 0 }
    $c = 0
    foreach ($ab in @($inner)) {
        if ($ab.details) { foreach ($d in @($ab.details)) { $c += [int]$d.total } }
        elseif ($null -ne $ab.total) { $c += [int]$ab.total }
    }
    return $c
}
# Interrupts breakdown: which enemy casts got interrupted, and by which class.
function IntBreak($report, $specMap) {
    $abil = @{}; $grp = @{}
    if ($report.intr -and $report.intr.data.entries) {
        $inner = @($report.intr.data.entries)[0].entries
        foreach ($ab in @($inner)) {
            $an = if ($ab.name) { [string]$ab.name } else { 'Unknown' }
            foreach ($d in @($ab.details)) {
                $c = [int]$d.total
                $abil[$an] = ([int]$abil[$an]) + $c
                $cls = if ($d.type) { [string]$d.type } else { 'Unknown' }
                $spec = if ($d.name -and $specMap.ContainsKey([string]$d.name)) { [string]$specMap[[string]$d.name] } else { '' }
                $key = "$spec|$cls"
                if (-not $grp.ContainsKey($key)) { $grp[$key] = [pscustomobject]@{ spec = $spec; class = $cls; count = 0 } }
                $grp[$key].count += $c
            }
        }
    }
    return @{ abilities = $abil; groups = $grp }
}
function IntCompare($oB, $tB, $oSpec, $tSpec) {
    $o = IntBreak $oB $oSpec; $t = IntBreak $tB $tSpec
    $abNames = @(@($o.abilities.Keys) + @($t.abilities.Keys)) | Sort-Object -Unique
    $abilities = @()
    foreach ($n in $abNames) { $abilities += [pscustomobject]@{ name = $n; ours = [int]$o.abilities[$n]; theirs = [int]$t.abilities[$n] } }
    $abilities = @($abilities | Sort-Object { - ([math]::Max($_.ours, $_.theirs)) })
    $keys = @(@($o.groups.Keys) + @($t.groups.Keys)) | Sort-Object -Unique
    $interrupters = @()
    foreach ($k in $keys) {
        $og = $o.groups[$k]; $tg = $t.groups[$k]
        $ref = if ($og) { $og } else { $tg }
        $interrupters += [pscustomobject]@{ spec = $ref.spec; class = $ref.class
            ours = [int]$(if ($og) { $og.count } else { 0 }); theirs = [int]$(if ($tg) { $tg.count } else { 0 }) }
    }
    $interrupters = @($interrupters | Sort-Object { - ([math]::Max($_.ours, $_.theirs)) })
    return [pscustomobject]@{ abilities = $abilities; interrupters = $interrupters }
}
$perBoss = @()
foreach ($b in $bosses) {
    $enc = [string]$b.encounterID
    $oB = Load-Boss $OursDir $enc; $tB = Load-Boss $TheirsDir $enc
    if (-not $oB -or -not $tB) { continue }
    $oDur = $oursFights[$enc].end - $oursFights[$enc].start
    $tDur = $theirsFights[$enc].end - $theirsFights[$enc].start
    $buffRows = @()
    foreach ($name in $keyBuffs) {
        if ($name -eq 'Heroism') { continue } # folded into Bloodlust row
        $oU = UptimePct $oB.buffs.data.auras $name $oDur
        $tU = UptimePct $tB.buffs.data.auras $name $tDur
        if ($oU -eq 0 -and $tU -eq 0) { continue }
        $buffRows += [pscustomobject]@{ name = $name; ours = $oU; theirs = $tU }
    }
    $debuffRows = @()
    foreach ($name in $keyDebuffs) {
        $oU = UptimePct $oB.debuffs.data.auras $name $oDur
        $tU = UptimePct $tB.debuffs.data.auras $name $tDur
        if ($oU -eq 0 -and $tU -eq 0) { continue }
        $debuffRows += [pscustomobject]@{ name = $name; ours = $oU; theirs = $tU }
    }
    $perBoss += [pscustomobject]@{ encounterID = $b.encounterID; name = $b.name
        oursLustSec = (LustSec $oB.buffs.data.auras $oursFights[$enc].start)
        theirsLustSec = (LustSec $tB.buffs.data.auras $theirsFights[$enc].start)
        buffs = $buffRows; debuffs = $debuffRows
        oursActivity = (ActivityPct $oB $oDur $oursDps); theirsActivity = (ActivityPct $tB $tDur $theirsDps)
        oursOverheal = (OverhealPct $oB $oursHeal);      theirsOverheal = (OverhealPct $tB $theirsHeal)
        oursDmgTaken = (DmgTakenExTanks $oB $oursTank);  theirsDmgTaken = (DmgTakenExTanks $tB $theirsTank)
        oursDurMs = $oDur; theirsDurMs = $tDur
        oursDtps = (Dtps (DmgTakenExTanks $oB $oursTank) $oDur); theirsDtps = (Dtps (DmgTakenExTanks $tB $theirsTank) $tDur)
        dmgCompare = (DmgCompare $oB $oursTank $tB $theirsTank 7)
        oursInterrupts = (CountActions $oB 'intr'); theirsInterrupts = (CountActions $tB 'intr')
        oursDispels = (CountActions $oB 'disp');    theirsDispels = (CountActions $tB 'disp')
        interrupts = (IntCompare $oB $tB $oursSpec $theirsSpec) }
}
function AvgNN($v) { $f = @($v | Where-Object { $_ -ne $null }); if ($f.Count) { Avg $f } else { 0 } }
# Overall DTPS is time-weighted (total damage / total fight time), not a mean of per-boss rates.
$oDmgSum = Sum ($perBoss | ForEach-Object { $_.oursDmgTaken });  $oDurSum = Sum ($perBoss | ForEach-Object { $_.oursDurMs })
$tDmgSum = Sum ($perBoss | ForEach-Object { $_.theirsDmgTaken }); $tDurSum = Sum ($perBoss | ForEach-Object { $_.theirsDurMs })
$quality = [pscustomobject]@{
    oursActivity   = AvgNN ($perBoss | ForEach-Object { $_.oursActivity });   theirsActivity = AvgNN ($perBoss | ForEach-Object { $_.theirsActivity })
    oursOverheal   = AvgNN ($perBoss | ForEach-Object { $_.oursOverheal });   theirsOverheal = AvgNN ($perBoss | ForEach-Object { $_.theirsOverheal })
    oursDmgTaken   = $oDmgSum; theirsDmgTaken = $tDmgSum
    oursDtps       = $(if ($oDurSum -gt 0) { [math]::Round($oDmgSum * 1000 / $oDurSum, 0) } else { 0 })
    theirsDtps     = $(if ($tDurSum -gt 0) { [math]::Round($tDmgSum * 1000 / $tDurSum, 0) } else { 0 })
    oursInterrupts = Sum ($perBoss | ForEach-Object { $_.oursInterrupts });   theirsInterrupts = Sum ($perBoss | ForEach-Object { $_.theirsInterrupts })
    oursDispels    = Sum ($perBoss | ForEach-Object { $_.oursDispels });      theirsDispels = Sum ($perBoss | ForEach-Object { $_.theirsDispels })
}

# ---------- CLEAR EFFICIENCY (wall-clock vs in-combat) ----------
function Efficiency($dir) {
    $fl = (ReadJson (Join-Path $dir 'fights.json')).reportData.report.fights
    $first = ($fl | Measure-Object -Property startTime -Minimum).Minimum
    $last  = ($fl | Measure-Object -Property endTime -Maximum).Maximum
    $combat = Sum ($fl | ForEach-Object { [long]$_.endTime - [long]$_.startTime })
    $span = [long]$last - [long]$first
    [pscustomobject]@{ spanMs = $span; combatMs = $combat; downtimeMs = ($span - $combat); kills = $fl.Count }
}
$efficiency = [pscustomobject]@{ ours = (Efficiency $OursDir); theirs = (Efficiency $TheirsDir) }

# ---------- ASSEMBLE + RENDER ----------
$payload = [pscustomobject]@{
    zone = $ZoneName; ours = @{ title = $OursName }; theirs = @{ title = $TheirsName }
    summary = $summary; bosses = $bosses
    deep = [pscustomobject]@{ composition = $composition; audit = $audit; quality = $quality; perBoss = $perBoss; efficiency = $efficiency }
}
$json = $payload | ConvertTo-Json -Depth 40 -Compress

$tplPath = Join-Path $PSScriptRoot '..\templates\report.html'
$utf8 = New-Object System.Text.UTF8Encoding($false)
$tpl = [System.IO.File]::ReadAllText($tplPath, [System.Text.Encoding]::UTF8)
$html = $tpl.Replace('/*__DATA__*/null', $json)
$outFull = if ([System.IO.Path]::IsPathRooted($OutFile)) { $OutFile } else { [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $OutFile)) }
$outDir = Split-Path -Parent $outFull
if ($outDir -and -not (Test-Path $outDir)) { New-Item -ItemType Directory -Force -Path $outDir | Out-Null }
[System.IO.File]::WriteAllText($outFull, $html, $utf8)
Write-Output "Deep-dive report written to $outFull ($($bosses.Count) shared bosses, $($perBoss.Count) with buff/debuff data)"
