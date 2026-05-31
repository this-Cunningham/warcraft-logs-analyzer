# introspect.ps1 — one-time GraphQL schema dump for the WCL public API.
# Saves the full introspection result to schema.json at the repo root so the
# skill (and you) can browse types/fields without guessing.
#
#   .\.claude\skills\warcraft-logs-analyzer\scripts\introspect.ps1

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'lib.ps1')

$introspection = @'
query IntrospectionQuery {
  __schema {
    queryType { name }
    mutationType { name }
    types {
      kind
      name
      description
      fields(includeDeprecated: true) {
        name
        description
        args { name description type { ...TypeRef } }
        type { ...TypeRef }
      }
      inputFields { name description type { ...TypeRef } }
      enumValues(includeDeprecated: true) { name description }
    }
  }
}
fragment TypeRef on __Type {
  kind name
  ofType { kind name ofType { kind name ofType { kind name ofType { kind name } } } }
}
'@

$data = Invoke-WclQuery -Query $introspection
$out = Join-Path (Find-RepoRoot) 'schema.json'
$data | ConvertTo-Json -Depth 40 | Set-Content -Path $out -Encoding utf8
Write-Output "Schema written to $out"
