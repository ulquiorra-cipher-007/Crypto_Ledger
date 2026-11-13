@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "PYTHONPATH=%~dp0;%PYTHONPATH%"
set "PYTHON_CMD="
set "DEBUG_MODE=0"

for %%a in (%*) do (
    if "%%a"=="--debug" set "DEBUG_MODE=1"
    if "%%a"=="--cli" set "DEBUG_MODE=1"
)

if "%DEBUG_MODE%"=="1" goto :use_console_python

:: 1. Check for pythonw on PATH
where pythonw >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PYTHON_CMD=pythonw"
    goto :launch_detached
)

:: 2. Check for pyw launcher
where pyw >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PYTHON_CMD=pyw -3"
    goto :launch_detached
)

:: 3. Check known Python install locations for pythonw.exe
if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
    goto :launch_detached
)

if exist "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe"
    goto :launch_detached
)

if exist "%LOCALAPPDATA%\Programs\Python\Python310\pythonw.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python310\pythonw.exe"
    goto :launch_detached
)

if exist "C:\Python312\pythonw.exe" (
    set "PYTHON_CMD=C:\Python312\pythonw.exe"
    goto :launch_detached
)

if exist "C:\Python313\pythonw.exe" (
    set "PYTHON_CMD=C:\Python313\pythonw.exe"
    goto :launch_detached
)

:use_console_python
:: Fallback: standard console python
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PYTHON_CMD=python"
    goto :launch_direct
)

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PYTHON_CMD=py -3"
    goto :launch_direct
)

echo [ERROR] Python was not found in PATH or standard installation directory.
pause
exit /b 1

:launch_detached
start "" "%PYTHON_CMD%" app.py %*
exit /b 0

:launch_direct
"%PYTHON_CMD%" app.py %*
if %ERRORLEVEL% NEQ 0 pause
exit /b %ERRORLEVEL%
