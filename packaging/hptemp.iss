#define MyAppName "HPTemp"
#ifndef MyAppVersion
  #define MyAppVersion "0.3.0"
#endif
#ifndef SourceRoot
  #define SourceRoot ".."
#endif
#define MyAppPublisher "XRFlow"
#define MyAppURL "https://github.com/XRFlow/HP-Temp"
#define MyAppExeName "HPTemp.exe"

[Setup]
AppId={{6EBA6A9D-AA69-467F-9257-EABD817F3D08}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
SourceDir={#SourceRoot}
LicenseFile=LICENSE
OutputDir=dist
OutputBaseFilename=HPTemp-{#MyAppVersion}-Setup
SetupIconFile=packaging\hptemp.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "autostart"; Description: "Start HPTemp when I log in"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "dist\HPTemp\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--minimized"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch HPTemp"; Flags: nowait postinstall skipifsilent
