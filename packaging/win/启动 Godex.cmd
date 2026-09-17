@echo off
title Godex Launcher (portable)
rem ============================================================
rem  Godex portable launcher - everything stays inside this folder
rem    engine/account data : data\godex-home   (CODEX_HOME)
rem    BYOK api keys       : data\godex-keys.env
rem    webview profile     : %APPDATA%\Godex (owl-app.ini)
rem  First run: python godex-byok.py  ->  option 5 (OAuth login)
rem  then re-run this file.
rem ============================================================
setlocal
set "GODEX_ROOT=%~dp0"
set "CODEX_HOME=%GODEX_ROOT%data\godex-home"

if not exist "%GODEX_ROOT%data\godex-home" mkdir "%GODEX_ROOT%data\godex-home" 2>nul

rem inject BYOK keys (KEY=VALUE per line) into process env
if exist "%GODEX_ROOT%data\godex-keys.env" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%GODEX_ROOT%data\godex-keys.env") do set "%%A=%%B"
)

start "" "%GODEX_ROOT%app\Godex.exe" %*
endlocal
