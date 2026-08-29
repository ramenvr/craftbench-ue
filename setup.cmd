@echo off
rem setup.cmd - execution-policy-proof launcher for setup.ps1: a fresh Windows box often has
rem PowerShell's Restricted policy, which blocks .\setup.ps1; batch files are exempt from it.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
exit /b %ERRORLEVEL%
