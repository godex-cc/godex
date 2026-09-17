Godex 0.0.1 (win32-x64, portable)
==================================

Godex is an independent desktop client for OpenAI-Codex-compatible workflows
with BYOK (bring your own key) model providers. All data stays inside this
folder; the official Codex app is not touched.

Quick start
-----------
1. First run must do the login ONCE from the command line:
       cd Godex-0.0.1-win32-x64
       python godex-byok.py        ->  choose 5 (OpenAI OAuth login)
   (the in-app login page needs chatgpt.com CDN access, so log in first)
2. Start the app:
       double-click  启动 Godex.cmd

Data layout (created on first run)
----------------------------------
  data\godex-home       engine/account data (CODEX_HOME)
  data\godex-keys.env   BYOK api keys, injected as env vars by the launcher
                        (keys are never written into config.toml)

Add BYOK providers (DeepSeek, Qwen, ...)
----------------------------------------
  python godex-byok.py   add / list / use / edit / del / status

Requirements
------------
  Windows 10/11 x64, Python 3.9+ only for the first-run login/CLI tool.
