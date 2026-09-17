; ============================================================
;  Godex 0.0.1 - Windows installer (NSIS, Unicode)
;  Packages the portable payload produced by packaging/common/make-zip.py
;  (stage dir: packaging/stage/Godex-<version>-win32-x64).
;
;  Build:  makensis packaging\win\godex.nsi
;  Output: packaging\dist\Godex-<version>-win32-x64-setup.exe
;
;  NSIS is NOT required to ship Godex - the portable zip is the primary
;  artifact. This installer only adds: Start-menu/desktop shortcuts,
;  an uninstaller and version metadata.
; ============================================================
Unicode true
ManifestDPIAware true

!define VERSION "0.0.1"
!ifndef STAGE
!define STAGE "..\stage\Godex-${VERSION}-win32-x64"
!endif
!define APPNAME "Godex"
!define UNINSTKEY "Godex"

Name "${APPNAME} ${VERSION}"
OutFile "..\dist\Godex-${VERSION}-win32-x64-setup.exe"
InstallDir "$LOCALAPPDATA\Godex"
InstallDirRegKey HKCU "Software\${UNINSTKEY}" "InstallDir"
RequestExecutionLevel user
SetCompressor lzma          ; per-file lzma (solid mode hits NSIS 2GB block limit on this payload)
ShowInstDetails show

VIProductVersion "0.0.1.0"
VIAddVersionKey "FileDescription" "${APPNAME} installer"
VIAddVersionKey "ProductName" "${APPNAME}"
VIAddVersionKey "FileVersion" "0.0.1"
VIAddVersionKey "ProductVersion" "0.0.1"
VIAddVersionKey "LegalCopyright" "Godex"

!define MUI_ICON "..\icons\godex-win.ico"
!define MUI_UNICON "..\icons\godex-win.ico"
!include "MUI2.nsh"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "English"

Section "Install"
  SetOutPath "$INSTDIR"
  File /r "${STAGE}\*"

  ; shortcuts (icon comes from app\Godex.exe which carries the brand face)
  CreateDirectory "$SMPROGRAMS\${APPNAME}"
  CreateShortcut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" "$INSTDIR\启动 Godex.cmd" "" "$INSTDIR\app\Godex.exe" 0 SW_SHOWMINIMIZED
  CreateShortcut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\启动 Godex.cmd" "" "$INSTDIR\app\Godex.exe" 0 SW_SHOWMINIMIZED

  WriteRegStr HKCU "Software\${UNINSTKEY}" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${UNINSTKEY}" "DisplayName" "${APPNAME}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${UNINSTKEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${UNINSTKEY}" "DisplayIcon" "$INSTDIR\app\Godex.exe,0"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${UNINSTKEY}" "UninstallString" "$INSTDIR\Uninstall.exe"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Uninstall"
  RMDir /r "$INSTDIR"
  RMDir /r "$SMPROGRAMS\${APPNAME}"
  Delete "$DESKTOP\${APPNAME}.lnk"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${UNINSTKEY}"
  DeleteRegKey HKCU "Software\${UNINSTKEY}"
  ; user data (data\godex-home, keys) lives under $INSTDIR too on portable
  ; installs; uncomment below to wipe it on uninstall:
  ; RMDir /r "$LOCALAPPDATA\Godex"
SectionEnd
