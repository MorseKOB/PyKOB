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

!define COMPANYNAME "PyKOB - MorseKOB in Python"
; GUID to use if needed: {76FE1177-7936-4E3F-B0C7-FADC19636D71}
;
!define OUR_GUID "{76FE1177-7936-4E3F-B0C7-FADC19636D71}"
!define REGKEY "Software\MKOB Suite"

;--------------------------------
;Include Modern UI

  !include "MUI2.nsh"

;--------------------------------
;General

  ;Name and file
  Name "MKOB Suite"
  OutFile "mkobsuite-install.exe"
  Unicode False  # Unicode installer will not work on Windows 95/98/ME

  ;Default installation folder
  InstallDir "$LOCALAPPDATA\mkob_suite"

  ;Get installation folder from registry if available
  InstallDirRegKey HKCU $REGKEY ""

  ;Request application privileges for Windows Vista/10/11
  RequestExecutionLevel user

;--------------------------------
;Variables

  Var StartMenuFolder

;--------------------------------
;Interface Settings

  !define MUI_ABORTWARNING

;--------------------------------
;Pages

  !insertmacro MUI_PAGE_WELCOME
  !insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
  !insertmacro MUI_PAGE_COMPONENTS
  !insertmacro MUI_PAGE_DIRECTORY

  ;Start Menu Folder Page Configuration
  !define MUI_STARTMENUPAGE_REGISTRY_ROOT "HKCU"
  !define MUI_STARTMENUPAGE_REGISTRY_KEY $REGKEY
  !define MUI_STARTMENUPAGE_REGISTRY_VALUENAME "Start Menu Folder"

  !insertmacro MUI_PAGE_STARTMENU Application $StartMenuFolder

  !insertmacro MUI_PAGE_INSTFILES
  !insertmacro MUI_PAGE_FINISH

  !insertmacro MUI_UNPAGE_WELCOME
  !insertmacro MUI_UNPAGE_CONFIRM
  !insertmacro MUI_UNPAGE_INSTFILES
  !insertmacro MUI_UNPAGE_FINISH

;--------------------------------
;Languages

  !insertmacro MUI_LANGUAGE "English"

;--------------------------------
;Installer Sections

Section "MKOB Suite - Base" SecInstBase
  SectionInstType RO
  SetOutPath "$INSTDIR"

  ;ADD YOUR OWN FILES HERE...

  ;Store installation folder
  WriteRegStr HKCU $REGKEY "" $INSTDIR

  ;Create uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  !insertmacro MUI_STARTMENU_WRITE_BEGIN Application

    ;Create shortcuts
    CreateDirectory "$SMPROGRAMS\$StartMenuFolder"
    CreateShortcut "$SMPROGRAMS\$StartMenuFolder\Uninstall.lnk" "$INSTDIR\Uninstall.exe"

  !insertmacro MUI_STARTMENU_WRITE_END

SectionEnd

Section "MKOB Suite - Utilities" SecInstUtils

  ;ADD YOUR OWN FILES HERE...

SectionEnd

Section "MKOB Suite - Documentation" SecInstDocs
  SetOutPath "$INSTDIR\Documentation"

  ;ADD YOUR OWN FILES HERE...

SectionEnd

/*
;--------------------------------
;Descriptions

  ;Language strings
  LangString DESC_SecInstMKS ${LANG_ENGLISH} "A test section."

  ;Assign language strings to sections
  !insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
    !insertmacro MUI_DESCRIPTION_TEXT ${SecInstBase} $(DESC_SecInstMKS)
  !insertmacro MUI_FUNCTION_DESCRIPTION_END
*/

;--------------------------------
;Uninstaller Section

Section "Uninstall"

  ;ADD YOUR OWN FILES HERE...

  Delete "$INSTDIR\Uninstall.exe"

  RMDir "$INSTDIR"

  DeleteRegKey /ifempty HKCU $REGKEY

SectionEnd
