@echo off
REM PeakLedger Forensic Workstation UI Launcher for Windows
cd /d "%~dp0"

where pythonw >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    start "" pythonw ui\main.py
    exit /b 0
)

where pyw >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    start "" pyw -3 ui\main.py
    exit /b 0
)

if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" (
    start "" "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" ui\main.py
    exit /b 0
)

if exist "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe" (
    start "" "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe" ui\main.py
    exit /b 0
)

if exist "%LOCALAPPDATA%\Programs\Python\Python310\pythonw.exe" (
    start "" "%LOCALAPPDATA%\Programs\Python\Python310\pythonw.exe" ui\main.py
    exit /b 0
)

:: Fallback
start "" python ui\main.py
exit /b 0
