:: Download MKOB.

@echo off
echo Installing MKOB...

:: Create new directory and download MKOB
chdir %HomePath%\Documents
mkdir MKOB4
chdir MKOB4
powershell (New-Object System.Net.WebClient).DownloadFile('https://github.com/MorseKOB/PyKOB/archive/master.zip','PyKOB.zip')

:: Unzip and remove the download file
powershell Expand-Archive -Force -LiteralPath PyKOB.zip -DestinationPath .
del PyKOB.zip

:: Create desktop shortcuts
powershell "$s=(New-Object -COM WScript.Shell).CreateShortcut('%HomePath%\Desktop\MKOB4.lnk');$s.TargetPath='%HomePath%\Documents\MKOB4\PYKOB-master\scripts\MKOB.cmd';$s.WorkingDirectory='%HomePath%\Documents\MKOB4\PYKOB-master\scripts';$s.Save()"
::powershell "$s=(New-Object -COM WScript.Shell).CreateShortcut('%HomePath%\Desktop\MKOB4 Scripts.lnk');$s.TargetPath='c:\Users\Les\Documents\MKOB4\PyKOB-master\scripts';$s.Save()"
powershell "$s=(New-Object -COM WScript.Shell).CreateShortcut('%HomePath%\Desktop\MKOB4 Scripts.lnk');$s.TargetPath='%HomePath%\Documents\MKOB4\PyKOB-master\scripts';$s.Save()"

echo Installation complete.
pause
