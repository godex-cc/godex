@echo off
title Godex Launcher
rem ============================================================
rem  Godex standalone launcher - fully isolated from official
rem  Codex data (engine auth, sessions, memories).
rem    engine/account data : data\godex-home   (CODEX_HOME)
rem    BYOK api keys       : data\godex-keys.env
rem    webview profile     : %APPDATA%\Godex (owl-app.ini)
rem  Configure models/keys:  python godex-byok.py
rem  First run: use godex-byok.py option 1 (OAuth) BEFORE
rem  launching, the in-app login page needs chatgpt.com CDN.
rem ============================================================
set "GODEX_ROOT=%~dp0"
set "CODEX_HOME=%GODEX_ROOT%\data\godex-home"

rem inject BYOK keys (KEY=VALUE per line) into process env
if exist "%GODEX_ROOT%\data\godex-keys.env" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%GODEX_ROOT%\data\godex-keys.env") do set "%%A=%%B"
)

start "" "%GODEX_ROOT%\app\Godex.exe" %*
