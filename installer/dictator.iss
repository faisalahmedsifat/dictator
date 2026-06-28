; Inno Setup Script for Dictator Voice Assistant
; Produces a professional Windows installer EXE

#define MyAppName "Dictator"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Dictator Project"
#define MyAppURL "https://github.com/dictator-voice/dictator"
#define MyAppExeName "Dictator.exe"

[Setup]
AppId={{A7B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=..\dist
OutputBaseFilename=DictatorSetup-{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Run at Windows startup"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "..\dist\Dictator\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\Dictator\logs"
Type: filesandordirs; Name: "{userappdata}\Dictator\config"

[Code]
// Clean up models directory on uninstall (with user confirmation)
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ModelsDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    ModelsDir := ExpandConstant('{userappdata}\Dictator\models');
    if DirExists(ModelsDir) then
    begin
      if MsgBox('Do you want to remove downloaded AI models (~1.5 GB)?',
                mbConfirmation, MB_YESNO) = IDYES then
      begin
        DelTree(ModelsDir, True, True, True);
      end;
    end;
    // Remove empty parent dir
    RemoveDir(ExpandConstant('{userappdata}\Dictator'));
  end;
end;
