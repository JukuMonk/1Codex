param([switch]$Quiet, [switch]$StatusOnly)
$ErrorActionPreference = 'Stop'
$gitOptionIndex = 0
if ($env:GIT_CONFIG_COUNT) { $gitOptionIndex = [int]$env:GIT_CONFIG_COUNT }
[Environment]::SetEnvironmentVariable("GIT_CONFIG_KEY_$gitOptionIndex", 'core.longpaths', 'Process')
[Environment]::SetEnvironmentVariable("GIT_CONFIG_VALUE_$gitOptionIndex", 'true', 'Process')
$env:GIT_CONFIG_COUNT = [string]($gitOptionIndex + 1)
$taskDir = Join-Path $env:USERPROFILE '.codex\1codex-updater'
$statusPath = Join-Path $taskDir 'status.json'
if ($StatusOnly) {
    if (Test-Path -LiteralPath $statusPath) { Get-Content -LiteralPath $statusPath -Raw }
    else { '{"schema_version":0,"status":"unknown","message":"No status recorded; rerun the current installer if needed."}' }
    return
}
New-Item -ItemType Directory -Path $taskDir -Force | Out-Null
$logPath = Join-Path $taskDir 'update.log'
$lastSuccess = $null
$installedVersion = $null
if (Test-Path -LiteralPath $statusPath) {
    try {
        $previous = Get-Content -LiteralPath $statusPath -Raw | ConvertFrom-Json
        $lastSuccess = $previous.last_success_at
        $installedVersion = $previous.installed_version
    } catch { }
}
function Write-UpdateStatus([string]$state, [string]$errorText) {
    $record = [ordered]@{schema_version=2; status=$state; last_attempt_at=(Get-Date -Format o);
        last_success_at=$lastSuccess; installed_version=$installedVersion; error=$errorText}
    $pending = $statusPath + '.pending'
    [IO.File]::WriteAllText($pending, ($record | ConvertTo-Json), (New-Object Text.UTF8Encoding($false)))
    if (Test-Path -LiteralPath $statusPath) { [IO.File]::Replace($pending, $statusPath, ($statusPath + '.previous')) }
    else { [IO.File]::Move($pending, $statusPath) }
}
try {
    $command = Get-Command codex -ErrorAction SilentlyContinue
    if ($command) { $codexExe = $command.Source }
    else {
        $candidate = Get-ChildItem -LiteralPath (Join-Path $env:LOCALAPPDATA 'OpenAI\Codex\bin') -Filter codex.exe -File -Recurse -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if (-not $candidate) { throw 'Codex CLI not found. Install or update the desktop app, or add Codex CLI to PATH.' }
        $codexExe = $candidate.FullName
    }
    $result = & $codexExe plugin marketplace upgrade 1codex --json 2>&1
    if ($LASTEXITCODE -ne 0) { throw ($result | Out-String) }
    $result2 = & $codexExe plugin add '1codex@1codex' --json 2>&1
    if ($LASTEXITCODE -ne 0) { throw ($result2 | Out-String) }
    $installed = ($result2 | Out-String) | ConvertFrom-Json
    $installedVersion = $installed.version
    $lastSuccess = Get-Date -Format o
    Write-UpdateStatus 'ok' ''
    @("$(Get-Date -Format o) OK", ($result | Out-String), ($result2 | Out-String)) | Set-Content -LiteralPath $logPath -Encoding UTF8
    if (-not $Quiet) { Write-Host '1Codex updated. Start a new chat; restart the desktop app if needed.' }
} catch {
    Write-UpdateStatus 'error' ([string]$_)
    "$(Get-Date -Format o) ERROR: $_" | Set-Content -LiteralPath $logPath -Encoding UTF8
    if (-not $Quiet) { Write-Error $_ }
    exit 1
}
