# Adds "Client Intake" shortcuts to the desktop and Start menu. Called by install.bat.
param([Parameter(Mandatory)][string]$PythonW)

$app = Join-Path $PSScriptRoot "client_intake.pyw"
$ws = New-Object -ComObject WScript.Shell
foreach ($dir in @([Environment]::GetFolderPath("Desktop"), [Environment]::GetFolderPath("Programs"))) {
    $lnk = $ws.CreateShortcut((Join-Path $dir "Client Intake.lnk"))
    $lnk.TargetPath = $PythonW
    $lnk.Arguments = "`"$app`""
    $lnk.WorkingDirectory = $PSScriptRoot
    $lnk.IconLocation = "shell32.dll,4"
    $lnk.Save()
}
