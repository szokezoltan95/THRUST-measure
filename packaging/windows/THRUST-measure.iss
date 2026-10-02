#define AppVersion "1.1.0"
[Setup]
AppId={{6B38A7E6-6633-4281-8596-78F8A60A275A}
AppName=THRUST-measure
AppVersion={#AppVersion}
AppPublisher=Zoltán Szőke
AppPublisherURL=https://github.com/szokezoltan95/THRUST-measure
DefaultDirName={localappdata}\Programs\THRUST-measure
DefaultGroupName=THRUST-measure
PrivilegesRequired=lowest
DisableDirPage=no
LicenseFile=..\..\EULA.txt
SetupIconFile=..\..\THRUST.ico
UninstallDisplayIcon={app}\THRUST-measure.exe
OutputDir=..\..\release
OutputBaseFilename=THRUST-measure-1.1.0-windows-x64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "..\..\dist\THRUST-measure\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\EULA.txt"; DestDir: "{app}"; Flags: ignoreversion

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: checkedonce

[Icons]
Name: "{group}\THRUST-measure"; Filename: "{app}\THRUST-measure.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\THRUST-measure"; Filename: "{app}\THRUST-measure.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\THRUST-measure.exe"; Description: "Launch THRUST-measure"; Flags: nowait postinstall skipifsilent
