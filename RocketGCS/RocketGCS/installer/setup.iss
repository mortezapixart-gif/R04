; installer\setup.iss
; -------------------------------------------------------------
; اسکریپت Inno Setup برای ساخت یک فایل نصب واقعی (Setup.exe) از
; خروجی PyInstaller (پوشهٔ dist\RocketGCS).
;
; نحوهٔ استفاده:
;   1) Inno Setup را نصب کنید (رایگان): https://jrsoftware.org/isinfo.php
;   2) این فایل را با Inno Setup Compiler باز کنید (یا از خط فرمان:
;        iscc installer\setup.iss
;      اجرا کنید) -- باید یک بار build.bat را زودتر اجرا کرده باشید
;      تا پوشهٔ dist\RocketGCS آماده باشد.
;   3) خروجی نهایی در installer\output\RocketGCS-Setup.exe ساخته می‌شود.
; -------------------------------------------------------------

#define MyAppName "کامپیوتر پرواز راکت"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "کانون علوم و فناوری‌های نوین ایران -- مرکز سمنان"
#define MyAppExeName "RocketGCS.exe"

[Setup]
AppId={{B6C1E9C2-5B3E-4B7A-9B7A-ROCKETGCS0001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\RocketGCS
DefaultGroupName=RocketGCS
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=RocketGCS-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; آیکون فایل نصب و برنامه
SetupIconFile=..\assets\rocketgcs.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "ایجاد آیکون روی دسکتاپ"; GroupDescription: "آیکون‌های اضافی:"

[Files]
; کل خروجی PyInstaller (exe + همهٔ کتابخانه‌ها/فایل‌های همراه) کپی می‌شود
Source: "..\dist\RocketGCS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\حذف {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "اجرای {#MyAppName}"; Flags: nowait postinstall skipifsilent
