$desktopPath = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktopPath "MediaForge AI.lnk"
$targetPath = Join-Path $PSScriptRoot "MediaForgeAI.bat"
$workingDir = $PSScriptRoot

$wshShell = New-Object -ComObject WScript.Shell
$shortcut = $wshShell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetPath
$shortcut.WorkingDirectory = $workingDir
$shortcut.Description = "MediaForge AI - Media Downloader & Video Translation Studio"
$shortcut.WindowStyle = 7 # Minimized launch
$shortcut.Save()

Write-Host "[MediaForge AI] Desktop shortcut created successfully at: $shortcutPath"
