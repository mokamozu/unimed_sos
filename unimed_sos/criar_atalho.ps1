$pasta = Split-Path -Parent $MyInvocation.MyCommand.Path
$html = Join-Path $pasta 'controle_treinamentos.html'
$ico  = Join-Path $pasta 'icone.ico'
$cands = @(
  "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
  "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
  "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
  "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
  "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe")
$nav = $cands | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $nav) { Write-Host 'Chrome ou Edge nao encontrado.'; exit 1 }
if (-not (Test-Path $html)) { Write-Host 'controle_treinamentos.html nao esta nesta pasta.'; exit 1 }
$url = ([System.Uri]$html).AbsoluteUri
$ws = New-Object -ComObject WScript.Shell
foreach ($destino in @($pasta, [Environment]::GetFolderPath('Desktop'))) {
  $lnk = $ws.CreateShortcut((Join-Path $destino 'Controle de Treinamentos SOS.lnk'))
  $lnk.TargetPath = $nav
  $lnk.Arguments = "--app=`"$url`""
  $lnk.IconLocation = "$ico,0"
  $lnk.WorkingDirectory = $pasta
  $lnk.Description = 'Controle de Treinamentos - SOS Emergencias Medicas'
  $lnk.Save()
}
Write-Host "Navegador usado: $nav"
