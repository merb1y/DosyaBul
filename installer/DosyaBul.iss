; DosyaBul 1.11.1 kurulum scripti (Inno Setup 6)
; Derleme: ISCC.exe installer\DosyaBul.iss

#define MyAppName "DosyaBul"
#define MyAppVersion "1.11.1"
#define MyAppPublisher "DosyaBul"
#define MyAppExeName "DosyaBul.exe"

[Setup]
AppId={{7E1F2C44-9B3A-4C0D-9E51-DOSYABUL190}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
LicenseFile=..\README.md
OutputDir=..
OutputBaseFilename=DosyaBul-Setup-{#MyAppVersion}
SetupIconFile=..\assets\icon.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startupicon"; Description: "Windows başlangıcında otomatik çalıştır"; GroupDescription: "Diğer görevler:"

[Files]
Source: "..\dist\DosyaBul\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{autostartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Ayarlar %LOCALAPPDATA%\DosyaBul içinde tutulur, kaldırıcıya dokunmaz.
Type: filesandordirs; Name: "{app}"

[Messages]
WelcomeLabel2=Bu sihirbaz [name/ver] kurulumunu tamamlayacak.%n%nKurulumdan önce DosyaBul çalışıyorsa kapatılacaktır.
SelectTasksDesc=Başka hangi ek görevler yapılsın?

[Code]
// Kurulumdan önce çalışan eski DosyaBul.exe'yi düzgün kapat
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Exec('taskkill.exe', '/f /im DosyaBul.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := True;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Exec('taskkill.exe', '/f /im DosyaBul.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;

// Kaldırırken başlangıç kısayolunu ve çalışan uygulamayı temizle
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    Exec('taskkill.exe', '/f /im DosyaBul.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    DeleteFile(ExpandConstant('{userstartup}\DosyaBul.lnk'));
    DeleteFile(ExpandConstant('{commonstartup}\DosyaBul.lnk'));
  end;
end;
