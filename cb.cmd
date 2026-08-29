@echo off
rem cb - repo-root shim so `.\cb <command>` works right after clone, no install.
rem The real launcher (python resolution + PYTHONPATH) is tools\run-agent\cb.cmd.
rem `setup.ps1` additionally pip-installs a PATH-wide `cb` (see tools\run-agent\pyproject.toml).
call "%~dp0tools\run-agent\cb.cmd" %*
