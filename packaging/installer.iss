#define AppName "GHMC Desktop Print Agent"
#ifndef AppVersion
  #define AppVersion "0.1.1"
#endif

[Setup]
AppId={{C7C920DD-16AB-48F7-8CA2-A66F71D871B2}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\GHMC\PrintAgent
DefaultGroupName=GHMC Print Agent
OutputDir=..\dist
OutputBaseFilename=GHMCPrintAgent-Setup-{#AppVersion}
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64
WizardStyle=modern
UninstallDisplayName={#AppName}
Compression=lzma2
SolidCompression=yes
SetupIconFile=..\assets\ghmc.ico

[Files]
Source: "{#GetEnv('GHMC_AGENT_STAGE')}\GHMCPrintAgent.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#GetEnv('GHMC_AGENT_STAGE')}\SumatraPDF.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#GetEnv('GHMC_AGENT_STAGE')}\start_agent.vbs"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Start or Resume GHMC Print Agent"; Filename: "{sys}\wscript.exe"; Parameters: """{app}\start_agent.vbs"""; IconFilename: "{app}\GHMCPrintAgent.exe"
Name: "{group}\Enroll or Resume GHMC Print Station"; Filename: "{app}\GHMCPrintAgent.exe"; Parameters: "--enroll --sumatra ""{app}\SumatraPDF.exe"""; IconFilename: "{app}\GHMCPrintAgent.exe"
Name: "{group}\Uninstall GHMC Print Agent"; Filename: "{uninstallexe}"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "GHMCPrintAgent"; ValueData: "wscript.exe ""{app}\start_agent.vbs"""; Flags: uninsdeletevalue

[Run]
Filename: "{app}\GHMCPrintAgent.exe"; Parameters: "--enroll --sumatra ""{app}\SumatraPDF.exe"""; Description: "Enroll or start this GHMC print station"; Flags: postinstall runasoriginaluser

[UninstallRun]
Filename: "{app}\GHMCPrintAgent.exe"; Parameters: "--remove-local-credential"; Flags: runhidden
