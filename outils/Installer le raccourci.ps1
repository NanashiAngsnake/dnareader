$ErrorActionPreference = 'Stop'
$base    = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonw = Join-Path $base '.venv\Scripts\pythonw.exe'
$script  = Join-Path $base 'lancer.pyw'
$icon    = Join-Path $base 'icon.ico'

if (-not (Test-Path $pythonw)) { Write-Host "pythonw.exe introuvable dans .venv" -Foreground Red; Read-Host; exit 1 }
if (-not (Test-Path $script))  { Write-Host "lancer.pyw introuvable" -Foreground Red; Read-Host; exit 1 }

$shell   = New-Object -ComObject WScript.Shell
$targets = @(
    (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Kanji Reader.lnk'),
    (Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs\Kanji Reader.lnk')
)

foreach ($t in $targets) {
    $dir = Split-Path -Parent $t
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    $lnk = $shell.CreateShortcut($t)
    $lnk.TargetPath       = $pythonw
    $lnk.Arguments        = '"' + $script + '"'
    $lnk.WorkingDirectory = $base
    $lnk.IconLocation     = $icon
    $lnk.Description      = 'Lecteur de japonais pour jeux video'
    $lnk.Save()
    Write-Host "Raccourci cree : $t" -Foreground Green
}

Write-Host ""
Write-Host "Termine. Lance Kanji Reader depuis le Bureau ou le menu Demarrer." -Foreground Cyan
Read-Host "Appuie sur Entree pour fermer"
