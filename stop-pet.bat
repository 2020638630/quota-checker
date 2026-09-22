@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ========================================
echo   Whale Maid Pet - Stop
echo ========================================
echo.

set KILLED=0
for %%I in (python.exe pythonw.exe) do (
    for /f "tokens=2 delims=," %%p in ('tasklist /fi "imagename eq %%I" /fo csv /nh 2^>nul') do (
        set PID=%%~p
        for /f "usebackq tokens=*" %%c in (`wmic process where "processid=!PID!" get commandline /value 2^>nul`) do (
            echo %%c | findstr /i "quota_pet.py" >nul
            if !errorlevel! equ 0 (
                echo   closing PID !PID! ...
                taskkill /PID !PID! /F >nul 2>nul
                if !errorlevel! equ 0 set /a KILLED+=1
            )
        )
    )
)

echo.
if "!KILLED!"=="0" (
    echo [i] No running pet found.
) else (
    echo [OK] Closed !KILLED! pet process^(es^).
)
echo.
ping -n 2 127.0.0.1 >nul
exit /b 0
