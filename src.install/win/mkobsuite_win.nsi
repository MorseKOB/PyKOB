/*
MIT License

Copyright (c) 2020-24 PyKOB - MorseKOB in Python

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
*/
;
; PyKOB (MKOB) Suite installer script for NSIS (Nullsoft Scriptable Install System)
;
; Note: Although this is 'PyKOB', most know it as 'MKOB'. Also, since it is being
;       installed as a binary, the Py'ness of it really isn't important.
;
; (refer to: NSIS/examples/example2.nsi and NSIS/examples/bigtest.nsi)

!define Company_Name "PyKOB - MorseKOB in Python"
!define Name "MKOB-Suite"

;
; GUID to use if needed: {76FE1177-7936-4E3F-B0C7-FADC19636D71}
;
!define Our_guid {76FE1177-7936-4E3F-B0C7-FADC19636D71}
!define Folder_name MKOB-Suite
!define Regkey "Software\${Name}"
;
; Packaged binaries (files to install) directory
;
!ifndef Package_dir
  !define Package_dir "..\..\bin\pkg\"
!endif
!define Package_core_dir "${Package_dir}core\"
!define Package_docs_dir "${Package_dir}docs\"
!define Package_utils_dir "${Package_dir}utils\"

;--------------------------------
;General

  ;Name and file
  Name ${Name}
  Caption "MKOB Suite Install"
  OutFile "mkobsuite-install.exe"
  Unicode False  # Unicode installer will not work on Windows 95/98/ME

  ;Default installation folder
  InstallDir "$PROFILE\${Folder_name}"

  ;Get installation folder from registry if available
  InstallDirRegKey HKCU ${Regkey} "Install_Dir"

  ;Request application privileges for Windows Vista/10/11
  RequestExecutionLevel user

;--------------------------------

; Pages

Page components
Page directory
Page instfiles

UninstPage uninstConfirm
UninstPage instfiles

;--------------------------------

; The stuff to install
Section "MKOB Core (required)"

  SectionIn RO

  ; Set output path to the installation directory.
  SetOutPath $INSTDIR

  ; Put files there
  File /r "${Package_core_dir}*.*"

  ; Write the installation path into the registry
  WriteRegStr HKLM ${Regkey} "Install_Dir" "$INSTDIR"

  ; Write the uninstall keys for Windows
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${Folder_name}" "DisplayName" "${Name}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${Folder_name}" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${Folder_name}" "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${Folder_name}" "NoRepair" 1
  WriteUninstaller "$INSTDIR\uninstall.exe"

SectionEnd

; Optional section - Utilities (can be disabled by the user)
Section "Utilities"

  ; Set output path to the installation directory.
  SetOutPath $INSTDIR

  ; Put utilities files there
  File /r "${Package_utils_dir}*.*"

  ; Flag that utilities were installed
  !define Utils_Installed

SectionEnd

; Optional section - Documentation (can be disabled by the user)
Section "Documentation"

  ; Set output path to the installation documentation directory.
  SetOutPath "$INSTDIR\Documentation"

  ; Put documentation files there
  File /r "${Package_docs_dir}*.*"

  ; Flag that docs were installed
  !define Docs_Installed

SectionEnd

; Optional section - Desktop and Start Menu Items (can be disabled by the user)
Section "Desktop & Start Menu Shortcuts"

  SetOutPath "$INSTDIR"

  CreateDirectory "$SMPROGRAMS\${Folder_name}"
  CreateShortcut "$SMPROGRAMS\${Folder_name}\Uninstall.lnk" "$INSTDIR\uninstall.exe"
  CreateShortcut "$SMPROGRAMS\${Folder_name}\Configure.lnk" "$INSTDIR\Configure.exe" "--gui"
  CreateShortcut "$SMPROGRAMS\${Folder_name}\MKOB.lnk" "$INSTDIR\MKOB.exe" "" "" 0 SW_SHOWMINIMIZED
  CreateShortcut "$DESKTOP\MKOB.lnk" "$INSTDIR\MKOB.exe" "" "" 0 SW_SHOWMINIMIZED
  !ifdef Docs_Installed
    CreateShortcut "$SMPROGRAMS\${Folder_name}\MKOB User Manual.lnk" "$INSTDIR\Documentation\User-Manual-MKOB4.pdf"
  !endif
  CreateShortcut "$SMPROGRAMS\${Folder_name}\MRT.lnk" "$INSTDIR\MRT.exe"
  !ifdef Utils_Installed
    CreateShortcut "$SMPROGRAMS\${Folder_name}\SysCheck.lnk" "$INSTDIR\SysCheck.exe"
  !endif

SectionEnd

;--------------------------------

; Uninstaller

Section "Uninstall"

  ; Remove registry keys
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${Folder_name}"
  DeleteRegKey HKLM ${Regkey}

  ; Remove files and uninstaller
  Delete $INSTDIR\*.*
  Delete $INSTDIR\uninstall.exe

  ; Remove shortcuts, if any
  Delete "$SMPROGRAMS\${Folder_name}\*.lnk"
  Delete "$DESKTOP\MKOB.lnk"
  ; Remove directories
  RMDir /r "$SMPROGRAMS\${Folder_name}"
  RMDir /r "$INSTDIR"

SectionEnd
