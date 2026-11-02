param([switch]$Quiet)
$ErrorActionPreference = 'Stop'
$gitOptionIndex = 0
if ($env:GIT_CONFIG_COUNT) { $gitOptionIndex = [int]$env:GIT_CONFIG_COUNT }
[Environment]::SetEnvironmentVariable("GIT_CONFIG_KEY_$gitOptionIndex", 'core.longpaths', 'Process')
[Environment]::SetEnvironmentVariable("GIT_CONFIG_VALUE_$gitOptionIndex", 'true', 'Process')
$env:GIT_CONFIG_COUNT = [string]($gitOptionIndex + 1)
$taskDir = Join-Path $env:USERPROFILE '.codex\1codex-updater'
New-Item -ItemType Directory -Path $taskDir -Force | Out-Null
$logPath = Join-Path $taskDir 'update.log'
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
    @("$(Get-Date -Format o) OK", ($result | Out-String), ($result2 | Out-String)) | Set-Content -LiteralPath $logPath -Encoding UTF8
    if (-not $Quiet) { Write-Host '1Codex updated. Start a new chat; restart the desktop app if needed.' }
} catch {
    "$(Get-Date -Format o) ERROR: $_" | Set-Content -LiteralPath $logPath -Encoding UTF8
    if (-not $Quiet) { Write-Error $_ }
    exit 1
}
