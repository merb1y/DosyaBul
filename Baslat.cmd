@echo off
chcp 65001 >nul
set "_PYI_APPLICATION_HOME_DIR="
set "_PYI_ARCHIVE_FILE="
set "_PYI_PARENT_PROCESS_LEVEL="
set "_PYI_SPLASH_IPC="
set "TCL_LIBRARY="
set "TK_LIBRARY="
if exist "%~dp0dist\DosyaBul.exe" (
    start "" "%~dp0dist\DosyaBul.exe"
    exit /b 0
)
where pythonw >nul 2>nul
if not errorlevel 1 (
    start "" pythonw "%~dp0run.py"
    exit /b 0
)
where pyw >nul 2>nul
if not errorlevel 1 (
    start "" pyw -3 "%~dp0run.py"
    exit /b 0
)
echo DosyaBul'u başlatmak için Python 3.10 veya daha yenisi gerekiyor.
echo Python'u https://www.python.org/downloads/windows/ adresinden kurabilirsin.
echo Alternatif: dist klasöründeki DosyaBul.exe Python gerektirmez.
pause
exit /b 1
