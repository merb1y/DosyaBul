param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'Programs\DosyaBul'),
    [string]$StartupDir = [Environment]::GetFolderPath('Startup'),
    [string]$ProgramsDir = [Environment]::GetFolderPath('Programs'),
    [switch]$NoLaunch
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Remove-Item Env:_PYI_APPLICATION_HOME_DIR -ErrorAction SilentlyContinue
Remove-Item Env:_PYI_ARCHIVE_FILE -ErrorAction SilentlyContinue
Remove-Item Env:_PYI_PARENT_PROCESS_LEVEL -ErrorAction SilentlyContinue
Remove-Item Env:_PYI_SPLASH_IPC -ErrorAction SilentlyContinue
Remove-Item Env:TCL_LIBRARY -ErrorAction SilentlyContinue
Remove-Item Env:TK_LIBRARY -ErrorAction SilentlyContinue

$sourceDir = Join-Path $PSScriptRoot 'dist\DosyaBul'
$source = Join-Path $sourceDir 'DosyaBul.exe'
if (-not (Test-Path -LiteralPath $source)) {
    throw "Dosya bulunamadı: $source`nÖnce ExeOlustur.ps1 çalıştırılmalı."
}

$target = Join-Path $installDir 'DosyaBul.exe'
$startMenu = Join-Path $ProgramsDir 'DosyaBul.lnk'
$startupLink = Join-Path $StartupDir 'DosyaBul.lnk'
$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'

$running = @(Get-Process -Name 'DosyaBul' -ErrorAction SilentlyContinue)
if ($running) {
    $running | Stop-Process -Force
    $deadline = [DateTime]::UtcNow.AddSeconds(10)
    while ((Get-Process -Name 'DosyaBul' -ErrorAction SilentlyContinue) -and [DateTime]::UtcNow -lt $deadline) {
        Start-Sleep -Milliseconds 100
    }
    if (Get-Process -Name 'DosyaBul' -ErrorAction SilentlyContinue) {
        throw 'Çalışan eski DosyaBul süreci kapatılamadı. Ctrl+Q ile kapatıp yeniden dene.'
    }
}
New-Item -ItemType Directory -Path $installDir -Force | Out-Null
New-Item -ItemType Directory -Path $ProgramsDir -Force | Out-Null
$copied = $false
for ($attempt = 1; $attempt -le 20 -and -not $copied; $attempt++) {
    try {
        # onedir modunda exe ve _internal klasörünün tamamı kopyalanır.
        Copy-Item -Path (Join-Path $sourceDir '*') -Destination $installDir -Recurse -Force
        $copied = $true
    } catch [System.IO.IOException] {
        if ($attempt -eq 20) { throw }
        Start-Sleep -Milliseconds 150
    }
}

$shell = New-Object -ComObject WScript.Shell
New-Item -Path $runKey -Force | Out-Null
Set-ItemProperty -Path $runKey -Name 'DosyaBul' -Value ('"{0}" --background' -f $target)
# Eski kurulum betiklerinin bıraktığı .lnk ile çift başlatmayı önle.
Remove-Item -LiteralPath $startupLink -Force -ErrorAction SilentlyContinue

$menuLink = $shell.CreateShortcut($startMenu)
$menuLink.TargetPath = $target
$menuLink.WorkingDirectory = $installDir
$menuLink.IconLocation = "$target,0"
$menuLink.Description = 'DosyaBul'
$menuLink.Save()

if (-not $NoLaunch) {
    Start-Process -FilePath $target
}
Write-Host 'DosyaBul hazır.'
Write-Host 'Varsayılan açma/gizleme: Alt + F2 (Ctrl+, ile tamamen değiştirilebilir)'
Write-Host 'Windows oturumu açıldığında arka planda başlayacak; panel ekrana gelmeyecek.'
