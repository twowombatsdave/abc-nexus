# Creates .env from .env.example if .env does not exist (repo root).
# Does not overwrite an existing .env.
# Run from repo root:  powershell -ExecutionPolicy Bypass -File scripts/init_local_env.ps1

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$template = Join-Path $root "dotenv.template"
$example = Join-Path $root ".env.example"
$target = Join-Path $root ".env"

if (Test-Path $target) {
    Write-Host ".env already exists — leaving it unchanged: $target"
    exit 0
}
$src = $template
if (-not (Test-Path $src)) {
    $src = $example
}
if (-not (Test-Path $src)) {
    Write-Host "Missing dotenv.template or .env.example at repo root."
    exit 1
}
Copy-Item -Path $src -Destination $target
Write-Host "Created $target — replace PASTE_… placeholders with your Asana PAT and workspace GID."
exit 0
