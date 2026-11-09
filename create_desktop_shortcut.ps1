# Create Windows Desktop Shortcut for SQLCLI Studio
$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [Environment]::GetFolderPath('Desktop')
$ShortcutPath = Join-Path $DesktopPath "SQLCLI Studio.lnk"
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)

$WorkspaceDir = (Get-Item -Path $PSScriptRoot).FullName
$PythonW = Join-Path $WorkspaceDir ".venv\Scripts\pythonw.exe"

if (-not (Test-Path $PythonW)) {
    $PythonW = (Get-Command python.exe).Source
}

$Shortcut.TargetPath = $PythonW
$Shortcut.Arguments = "-m sqlcli.cli"
$Shortcut.WorkingDirectory = $WorkspaceDir
$Shortcut.Description = "SQLCLI - Native Desktop Database Studio"
$Shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,269"
$Shortcut.Save()

Write-Host "Created Desktop Shortcut: $ShortcutPath"
