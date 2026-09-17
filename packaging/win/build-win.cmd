@echo off
rem ============================================================
rem  Godex Windows build entry (version comes from packaging\VERSION)
rem    1. regenerate the icon set (ico/icns/png)
rem    2. stage + zip  ->  packaging\dist\Godex-<v>-win32-x64.zip (+ manifest)
rem    3. optional NSIS installer if makensis is on PATH
rem ============================================================
setlocal
cd /d "%~dp0.."

python packaging\common\make-icons.py || goto :err
python packaging\common\make-zip.py || goto :err

where makensis >nul 2>nul
if %errorlevel%==0 (
  makensis packaging\win\godex.nsi || goto :err
) else (
  echo [skip] makensis not found - portable zip is the shipped artifact
)

exit /b 0
:err
exit /b 1
