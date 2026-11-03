$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
# Tek-dosya PyInstaller süreçlerinden kalabilen geçici Tcl/Tk yolları yeni
# test ve paketlemeyi bozmamalı; sistem Python'u kendi gerçek Tcl dizinini bulur.
Remove-Item Env:TCL_LIBRARY -ErrorAction SilentlyContinue
Remove-Item Env:TK_LIBRARY -ErrorAction SilentlyContinue
Remove-Item Env:TCLLIBPATH -ErrorAction SilentlyContinue
Remove-Item Env:_PYI_APPLICATION_HOME_DIR -ErrorAction SilentlyContinue
Remove-Item Env:_PYI_ARCHIVE_FILE -ErrorAction SilentlyContinue
Remove-Item Env:_PYI_PARENT_PROCESS_LEVEL -ErrorAction SilentlyContinue
Remove-Item Env:_PYI_SPLASH_IPC -ErrorAction SilentlyContinue
Push-Location $PSScriptRoot
try {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        throw 'Python 3.10 veya daha yenisini kurup PATH seçeneğini etkinleştir.'
    }
    $env:PYTHONIOENCODING = 'utf-8'
    Write-Host 'Otomatik testler çalıştırılıyor...'
    & python -m unittest discover -s tests -t "$PSScriptRoot" -v
    if ($LASTEXITCODE -ne 0) { throw 'Testler başarısız; EXE oluşturulmadı.' }

    & python -c 'import PyInstaller'
    if ($LASTEXITCODE -ne 0) {
        throw 'Paketleme aracını kur: python -m pip install "pyinstaller>=6,<7"'
    }
    & python tools/create_icons.py
    if ($LASTEXITCODE -ne 0) { throw 'Uygulama simgesi oluşturulamadı.' }

    # Önceki derlemeden kalan tek-dosya DosyaBul.exe karışıklık yaratmasın;
    # dist klasörünü baştan oluştur.
    $dist = Join-Path $PSScriptRoot 'dist'
    if (Test-Path $dist) { Remove-Item -Recurse -Force $dist -ErrorAction SilentlyContinue }

    Write-Host 'Windows uygulaması paketleniyor...'
    # Tek-dosya (--onefile) modu, kapanışta açık kalan dosya tutamaçları yüzünden
    # "failed to remove temporary directory: _MEI..." uyarısı üretebiliyor.
    # Klasör (--onedir) modunda geçici klasör hiç açılmadığı için bu hata oluşmaz.
    & python -m PyInstaller --noconfirm --windowed --name DosyaBul --icon assets/icon.ico --add-data 'assets/icon.png;assets' --version-file assets/version_info.txt run.py
    if ($LASTEXITCODE -ne 0) { throw 'EXE oluşturulamadı.' }
    Write-Host "Hazır: $PSScriptRoot\dist\DosyaBul\DosyaBul.exe"
} finally {
    Pop-Location
}
