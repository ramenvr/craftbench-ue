@echo off
rem cb - thin launcher for the cross-platform CraftBench x Aura CLI (aura_rig/cb.py).
rem
rem Lets you type:   cb <command> [flags]
rem instead of:      py -3 -m aura_rig.cb <command> [flags]
rem
rem What it bakes in (so you never type them):
rem   Python pick     first working Python 3.11+ of: py -3.12 -> py -3 -> python -> python3
rem                   (override by setting CB_PYLAUNCH, e.g.  set CB_PYLAUNCH=python )
rem   -m aura_rig.cb  run the cb package module as a script (-m is a Python flag, not a cb flag)
rem   PYTHONPATH      points at this folder so `aura_rig` resolves from ANY current directory
rem
rem Run from anywhere by putting this folder on PATH, or call it by path
rem (tools\run-agent\cb ...). In PowerShell from this folder use  .\cb  (or add to PATH).
setlocal
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
set "CB_PY="
if defined CB_PYLAUNCH (
  %CB_PYLAUNCH% -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
  if not errorlevel 1 (
    set "CB_PY=%CB_PYLAUNCH%"
  ) else (
    echo cb: cannot start Python 3.11+ via CB_PYLAUNCH="%CB_PYLAUNCH%". 1>&2
    echo   Unset CB_PYLAUNCH to use the built-in fallback chain, or point it at a Python 3.11+ exe. 1>&2
    exit /b 9
  )
)
if not defined CB_PY for %%C in ("py -3.12" "py -3" "python" "python3") do if not defined CB_PY (
  %%~C -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
  if not errorlevel 1 set "CB_PY=%%~C"
)
if not defined CB_PY (
  echo cb: no working Python 3.11+ found ^(tried py -3.12, py -3, python, python3^). 1>&2
  echo   Fix: install Python 3.11+ ^(3.12 recommended^) so `py -3 --version` works, 1>&2
  echo        or set CB_PYLAUNCH to a Python 3.11+ exe, e.g.  set CB_PYLAUNCH=python 1>&2
  echo   Then run setup.ps1 once - it pip-installs a PATH-wide `cb` and reports readiness. 1>&2
  echo   To only GRADE tasks you do not need cb - see the README grade-only tier. 1>&2
  exit /b 9
)
%CB_PY% -m aura_rig.cb %*
