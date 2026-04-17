#ifndef AppName
  #error AppName define is required.
#endif
#ifndef AppVersion
  #error AppVersion define is required.
#endif
#ifndef AppPublisher
  #error AppPublisher define is required.
#endif
#ifndef AppExeName
  #error AppExeName define is required.
#endif
#ifndef AppId
  #error AppId define is required.
#endif
#ifndef SourceExe
  #error SourceExe define is required.
#endif
#ifndef IconFile
  #error IconFile define is required.
#endif
#ifndef OutputDir
  #error OutputDir define is required.
#endif
#ifndef OutputBaseFilename
  #error OutputBaseFilename define is required.
#endif

[Setup]
AppId={{{#AppId}}}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
CloseApplications=force
CloseApplicationsFilter={#AppExeName}
RestartApplications=no
OutputDir={#OutputDir}
OutputBaseFilename={#OutputBaseFilename}
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "{#SourceExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
