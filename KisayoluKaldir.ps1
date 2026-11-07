param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'Programs\DosyaBul'),
    [string]$StartupDir = [Environment]::GetFolderPath('Startup'),
    [string]$ProgramsDir = [Environment]::GetFolderPath('Programs')
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$startupLink = Join-Path $StartupDir 'DosyaBul.lnk'
$startMenuLink = Join-Path $ProgramsDir 'DosyaBul.lnk'

Get-Process -Name 'DosyaBul' -ErrorAction SilentlyContinue | Stop-Process -Force
Remove-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'DosyaBul' -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $startupLink -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $startMenuLink -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $installDir -Recurse -Force -ErrorAction SilentlyContinue
@(
    'HKCU:\Software\Classes\exefile\shell\DosyaBulPin',
    'HKCU:\Software\Classes\lnkfile\shell\DosyaBulPin',
    'HKCU:\Software\Classes\InternetShortcut\shell\DosyaBulPin',
    'HKCU:\Software\Classes\SystemFileAssociations\.exe\shell\DosyaBulPin',
    'HKCU:\Software\Classes\SystemFileAssociations\.lnk\shell\DosyaBulPin'
) | ForEach-Object { Remove-Item -LiteralPath $_ -Recurse -Force -ErrorAction SilentlyContinue }
Write-Host 'DosyaBul otomatik başlangıçtan ve Başlat menüsünden kaldırıldı.'
Write-Host 'Arama indeksi korunuyor: %LOCALAPPDATA%\DosyaBul'
