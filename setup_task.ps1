<#
Enregistre une tâche planifiée Windows qui exécute ticket_watcher.py toutes les 15 minutes.
Exécuter ce script une seule fois (en tant qu'utilisateur courant, pas besoin d'admin) :
    powershell -ExecutionPolicy Bypass -File .\setup_task.ps1
#>

$TaskName   = "FanPassTicketWatcher"
$ScriptDir  = $PSScriptRoot
$PythonExe  = (Get-Command python).Source
$ScriptPath = Join-Path $ScriptDir "ticket_watcher.py"

$Action  = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$ScriptPath`"" -WorkingDirectory $ScriptDir
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration ([TimeSpan]::MaxValue)
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Force

Write-Host "Tâche planifiée '$TaskName' créée : exécution toutes les 15 minutes."
