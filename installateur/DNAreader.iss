#define Nom       "DNAreader"
#ifndef Version
  #define Version   "1.0.0"
#endif
#define Editeur   "DNAreader"
#define Exe       "DNAreader.exe"

[Setup]
AppId={{8E5C1F42-2C7A-4A1B-9E3D-DNAREADER0001}
AppName={#Nom}
AppVersion={#Version}
AppVerName={#Nom} {#Version}
AppPublisher={#Editeur}
DefaultDirName={autopf}\{#Nom}
DefaultGroupName={#Nom}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename={#Nom}-Setup-{#Version}
SetupIconFile=..\ressources\icon.ico
UninstallDisplayIcon={app}\{#Exe}
UninstallDisplayName={#Nom} {#Version}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\NOTICE.md
InfoBeforeFile=
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "bureau"; Description: "Créer un raccourci sur le Bureau"; \
  GroupDescription: "Raccourcis :"
Name: "demarrage"; Description: "Lancer DNAreader au démarrage de Windows"; \
  GroupDescription: "Options :"; Flags: unchecked

[Files]
Source: "..\dist\DNAreader\*"; DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\NOTICE.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#Nom}"; Filename: "{app}\{#Exe}"
Name: "{group}\Désinstaller {#Nom}"; Filename: "{uninstallexe}"
Name: "{group}\Licences et crédits"; Filename: "{app}\NOTICE.md"
Name: "{autodesktop}\{#Nom}"; Filename: "{app}\{#Exe}"; Tasks: bureau
Name: "{userstartup}\{#Nom}"; Filename: "{app}\{#Exe}"; Tasks: demarrage

[Run]
Filename: "{app}\{#Exe}"; Description: "Lancer {#Nom}"; \
  Flags: nowait postinstall skipifsilent
Filename: "{app}\{#Exe}"; Flags: nowait runasoriginaluser; \
  Check: RelanceDemandee

[UninstallDelete]
Type: filesandordirs; Name: "{app}\__pycache__"

[Code]
function RelanceDemandee(): Boolean;
begin
  Result := ExpandConstant('{param:RELANCE|0}') = '1';
end;

function WebView2Installe(): Boolean;
var
  s: String;
begin
  Result :=
    RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', s) or
    RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', s) or
    RegQueryStringValue(HKCU, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', s);
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if not WebView2Installe() then
  begin
    if MsgBox(
      'DNAreader affiche son interface avec le WebView2 Runtime de Microsoft,'
      + ' qui ne semble pas installé sur cette machine.' + #13#10#13#10
      + 'Sans lui, la fenêtre de l''application restera blanche.' + #13#10#13#10
      + 'Windows 11 le fournit d''origine. Sur Windows 10, il s''installe'
      + ' gratuitement depuis le site de Microsoft :' + #13#10
      + 'https://developer.microsoft.com/microsoft-edge/webview2/' + #13#10#13#10
      + 'Continuer l''installation quand même ?',
      mbConfirmation, MB_YESNO) = IDNO then
      Result := False;
  end;
end;
