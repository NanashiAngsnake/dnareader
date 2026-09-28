#ifndef Version
  #define Version   "1.0.0"
#endif
#ifndef SetupHash
  #define SetupHash ""
#endif
#ifndef Depot
  #define Depot     "NanashiAngsnake/dnareader-releases"
#endif
#define Nom       "DNAreader"
#define Complet   Nom + "-Setup-" + Version + ".exe"
#define Adresse   "https://github.com/" + Depot + "/releases/download/v" + Version + "/" + Complet

[Setup]
AppId={{8E5C1F42-2C7A-4A1B-9E3D-DNAREADER0001}
AppName={#Nom}
AppVersion={#Version}
AppPublisher={#Nom}
CreateAppDir=no
Uninstallable=no
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename={#Nom}-WebSetup-{#Version}
SetupIconFile=..\ressources\icon.ico
WizardStyle=modern
ArchitecturesAllowed=x64compatible
DisableWelcomePage=no
AppendDefaultDirName=no

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Messages]
fr.WelcomeLabel2=Ce programme va télécharger {#Nom} {#Version} (environ 122 Mo) puis l'installer.%n%nRien n'est conservé de ce téléchargement une fois l'installation terminée.
en.WelcomeLabel2=This program will download {#Nom} {#Version} (about 122 MB) and install it.%n%nNothing from the download is kept afterwards.

[Code]
var
  PageTelechargement: TDownloadWizardPage;

procedure InitializeWizard();
begin
  PageTelechargement := CreateDownloadPage(
    SetupMessage(msgWizardPreparing), SetupMessage(msgPreparingDesc), nil);
  PageTelechargement.ShowBaseNameInsteadOfUrl := True;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Code: Integer;
begin
  Result := True;
  if CurPageID <> wpReady then Exit;

  PageTelechargement.Clear;
  PageTelechargement.Add('{#Adresse}', '{#Complet}', '{#SetupHash}');
  PageTelechargement.Show;
  try
    try
      PageTelechargement.Download;
    except
      if PageTelechargement.AbortedByUser then
        Log('Téléchargement interrompu par l''utilisateur.')
      else
        SuppressibleMsgBox('Le téléchargement a échoué :'#13#10#13#10
          + GetExceptionMessage + #13#10#13#10
          + 'Vérifie ta connexion, ou télécharge l''installateur complet depuis'#13#10
          + 'https://github.com/{#Depot}/releases/latest',
          mbCriticalError, MB_OK, IDOK);
      Result := False;
      Exit;
    end;
  finally
    PageTelechargement.Hide;
  end;

  if not Exec(ExpandConstant('{tmp}\{#Complet}'), '/SILENT /RELANCE=1',
              '', SW_SHOW, ewWaitUntilTerminated, Code) then
  begin
    SuppressibleMsgBox('L''installateur téléchargé n''a pas démarré.',
      mbCriticalError, MB_OK, IDOK);
    Result := False;
    Exit;
  end;
  if Code <> 0 then
  begin
    SuppressibleMsgBox(Format('L''installation s''est arrêtée (code %d).', [Code]),
      mbCriticalError, MB_OK, IDOK);
    Result := False;
  end;
end;
