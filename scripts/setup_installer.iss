#define MyAppName "SocialPetaDownloader"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Your Company"
#define MyAppExeName "SocialPetaDownloader.exe"

[Setup]
; AppId uniquely identifies this application.
AppId={{FD58B0A8-9444-42B1-ABCA-EABF26F451F3}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
; Install to Local AppData so admin rights are not required to download videos
DefaultDirName={localappdata}\Programs\{#MyAppName}
DisableProgramGroupPage=yes
; Output location
OutputDir={#MyOutputDir}
OutputBaseFilename={#MyAppName} Setup {#MyAppVersion}
SetupIconFile={#MyProjectDir}frontends\socialpeta_downloader\app\favicon.ico
Compression=lzma2/ultra64
SolidCompression=yes
; PrivilegesRequired=lowest means it won't ask for Administrator permissions
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#MyDistDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
