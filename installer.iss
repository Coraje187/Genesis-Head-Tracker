[Setup]
AppName=Genesis Head Tracker
AppVersion=1.0.2
AppPublisher=Coraje187
AppPublisherURL=https://github.com/Coraje187/Genesis-Head-Tracker
DefaultDirName={autopf}\Genesis Head Tracker
DefaultGroupName=Genesis Head Tracker
AllowNoIcons=yes
OutputDir=dist
OutputBaseFilename=Genesis-Head-Tracker-Setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\GenesisHeadTracker.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\GenesisHeadTracker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Genesis Head Tracker"; Filename: "{app}\GenesisHeadTracker.exe"; IconFilename: "{app}\assets\icon.ico"
Name: "{group}\{cm:UninstallProgram,Genesis Head Tracker}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Genesis Head Tracker"; Filename: "{app}\GenesisHeadTracker.exe"; IconFilename: "{app}\assets\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\GenesisHeadTracker.exe"; Description: "{cm:LaunchProgram,Genesis Head Tracker}"; Flags: nowait postinstall skipifsilent
