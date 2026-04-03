# Creates .env from .env.example if .env does not exist (repo root).
# Does not overwrite an existing .env.
# Run from repo root:  powershell -ExecutionPolicy Bypass -File scripts/init_local_env.ps1

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$example = Join-Path $root ".env.example"
$target = Join-Path $root ".env"

if (Test-Path $target) {
    Write-Host ".env already exists — leaving it unchanged: $target"
    exit 0
}
if (-not (Test-Path $example)) {
    Write-Host "Missing .env.example at: $example"
    exit 1
}
Copy-Item -Path $example -Destination $target
Write-Host "Created $target — edit it and add ASANA_ACCESS_TOKEN and ASANA_WORKSPACE_GID."
exit 0
