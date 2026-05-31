# lib.ps1 — shared helpers for the Warcraft Logs Analyzer skill.
# Dot-source this:  . .\.claude\skills\warcraft-logs-analyzer\scripts\lib.ps1
#
# Provides:
#   Get-WclConfig    -> reads client_id/secret from env vars or repo .env
#   Get-WclToken     -> fetches + caches a client-credentials bearer token
#   Invoke-WclQuery  -> POSTs a GraphQL query to the public v2/client endpoint

$script:WclTokenUri = 'https://www.warcraftlogs.com/oauth/token'
$script:WclApiUri    = 'https://www.warcraftlogs.com/api/v2/client'

function Find-RepoRoot {
    # Walk up from the current location looking for a .git directory.
    $dir = (Get-Location).Path
    while ($dir) {
        if (Test-Path (Join-Path $dir '.git')) { return $dir }
        $parent = Split-Path $dir -Parent
        if ($parent -eq $dir) { break }
        $dir = $parent
    }
    return (Get-Location).Path
}

function Get-WclConfig {
    # Precedence: explicit env vars win, otherwise parse repo-root\.env
    $id     = $env:WCL_CLIENT_ID
    $secret = $env:WCL_CLIENT_SECRET

    if (-not $id -or -not $secret) {
        $envFile = Join-Path (Find-RepoRoot) '.env'
        if (Test-Path $envFile) {
            foreach ($line in Get-Content $envFile) {
                $trimmed = $line.Trim()
                if (-not $trimmed -or $trimmed.StartsWith('#')) { continue }
                $eq = $trimmed.IndexOf('=')
                if ($eq -lt 1) { continue }
                $key = $trimmed.Substring(0, $eq).Trim()
                $val = $trimmed.Substring($eq + 1).Trim().Trim('"').Trim("'")
                if ($key -eq 'WCL_CLIENT_ID'     -and -not $id)     { $id = $val }
                if ($key -eq 'WCL_CLIENT_SECRET' -and -not $secret) { $secret = $val }
            }
        }
    }

    if (-not $id -or -not $secret) {
        throw "Missing credentials. Set WCL_CLIENT_ID and WCL_CLIENT_SECRET as env vars or in a .env file at the repo root (copy .env.example)."
    }
    return @{ ClientId = $id; ClientSecret = $secret }
}

function Get-WclToken {
    param([switch]$Force)

    $cacheFile = Join-Path (Find-RepoRoot) '.wcl-token.json'

    if (-not $Force -and (Test-Path $cacheFile)) {
        try {
            $cached = Get-Content $cacheFile -Raw | ConvertFrom-Json
            # expires_at is an ISO8601 string; refresh a day early to be safe.
            if ($cached.access_token -and [datetime]$cached.expires_at -gt (Get-Date).AddDays(1)) {
                return $cached.access_token
            }
        } catch { }  # fall through to refetch on any cache problem
    }

    $cfg   = Get-WclConfig
    $pair  = "$($cfg.ClientId):$($cfg.ClientSecret)"
    $basic = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($pair))

    $resp = Invoke-RestMethod -Uri $script:WclTokenUri -Method Post `
        -Headers @{ Authorization = "Basic $basic" } `
        -Body @{ grant_type = 'client_credentials' }

    $expiresAt = (Get-Date).AddSeconds([int]$resp.expires_in).ToString('o')
    @{ access_token = $resp.access_token; expires_at = $expiresAt } |
        ConvertTo-Json | Set-Content -Path $cacheFile -Encoding utf8

    return $resp.access_token
}

function Invoke-WclQuery {
    param(
        [Parameter(Mandatory)][string]$Query,
        [hashtable]$Variables,
        [int]$Depth = 30
    )

    $token = Get-WclToken
    $payload = @{ query = $Query }
    if ($Variables) { $payload.variables = $Variables }
    $body = $payload | ConvertTo-Json -Depth 20 -Compress

    $resp = Invoke-RestMethod -Uri $script:WclApiUri -Method Post `
        -Headers @{ Authorization = "Bearer $token"; 'Content-Type' = 'application/json' } `
        -Body $body

    if ($resp.PSObject.Properties.Name -contains 'errors' -and $resp.errors) {
        throw "GraphQL errors: $($resp.errors | ConvertTo-Json -Depth 10)"
    }
    return $resp.data
}
