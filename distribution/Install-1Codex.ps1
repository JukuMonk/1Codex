param([switch]$NoSchedule)
$ErrorActionPreference = 'Stop'
# Enable long checkout paths for child Git commands only; keep user Git settings intact.
$gitOptionIndex = 0
if ($env:GIT_CONFIG_COUNT) { $gitOptionIndex = [int]$env:GIT_CONFIG_COUNT }
[Environment]::SetEnvironmentVariable("GIT_CONFIG_KEY_$gitOptionIndex", 'core.longpaths', 'Process')
[Environment]::SetEnvironmentVariable("GIT_CONFIG_VALUE_$gitOptionIndex", 'true', 'Process')
$env:GIT_CONFIG_COUNT = [string]($gitOptionIndex + 1)
$taskDir = Join-Path $env:USERPROFILE '.codex\1codex-updater'
$command = Get-Command codex -ErrorAction SilentlyContinue
if ($command) { $codexExe = $command.Source }
else {
    $candidate = Get-ChildItem -LiteralPath (Join-Path $env:LOCALAPPDATA 'OpenAI\Codex\bin') -Filter codex.exe -File -Recurse -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $candidate) { throw 'Codex CLI not found. Install or update the desktop app, or add Codex CLI to PATH.' }
    $codexExe = $candidate.FullName
}
& $codexExe plugin marketplace add 'https://github.com/JukuMonk/1Codex.git' --ref plugin
if ($LASTEXITCODE -ne 0) { throw 'Cannot add the 1Codex marketplace. Check network access and the desktop app version.' }
& $codexExe plugin add '1codex@1codex' --json
if ($LASTEXITCODE -ne 0) { throw 'Cannot install 1Codex. Update the desktop app and retry.' }
New-Item -ItemType Directory -Path $taskDir -Force | Out-Null
$updater = Join-Path $taskDir 'Update-1Codex.ps1'
$sourceUpdater = Join-Path $PSScriptRoot 'Update-1Codex.ps1'
if (-not (Test-Path -LiteralPath $sourceUpdater)) { throw 'Place Update-1Codex.ps1 beside the installer.' }
Copy-Item -LiteralPath $sourceUpdater -Destination $updater -Force
if (-not $NoSchedule) {
    $shellExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $action = New-ScheduledTaskAction -Execute $shellExe -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -File "' + $updater + '" -Quiet')
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
    $triggers = @((New-ScheduledTaskTrigger -Daily -At '12:00'), (New-ScheduledTaskTrigger -AtLogOn -User ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)))
    $principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName '1Codex-Update' -Action $action -Trigger $triggers -Settings $settings -Principal $principal -Force | Out-Null
}
Write-Host '1Codex installed. Restart the desktop app and start a new chat.'
Write-Host 'Daily updates: 12:00 and user sign-in. Log: ~/.codex/1codex-updater/update.log'
