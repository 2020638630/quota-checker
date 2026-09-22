@echo off
cd /d "%~dp0"

echo ========================================
echo   Whale Maid Pet - Start
echo ========================================
echo.

set RUNNING=0
for /f "tokens=2 delims=," %%p in ('tasklist /fi "imagename eq python.exe" /fo csv /nh 2^>nul') do (
    for /f "usebackq tokens=*" %%c in (`wmic process where "processid=%%~p" get commandline /value 2^>nul ^| findstr /i "quota_pet.py"`) do set RUNNING=1
)
for /f "tokens=2 delims=," %%p in ('tasklist /fi "imagename eq pythonw.exe" /fo csv /nh 2^>nul') do (
    for /f "usebackq tokens=*" %%c in (`wmic process where "processid=%%~p" get commandline /value 2^>nul ^| findstr /i "quota_pet.py"`) do set RUNNING=1
)

if "%RUNNING%"=="1" (
    echo [!] Pet is already running.
    echo     To restart, run stop-pet.bat first.
    echo.
    exit /b 0
)

where python >nul 2>nul
if errorlevel 1 (
    echo [X] python not found in PATH. Install Python 3.8+ first.
    echo.
    exit /b 1
)

if not exist "quotas.json" (
    echo [!] quotas.json missing, creating template...
    python quota.py --init
    echo     Fill in your DeepSeek API key afterwards.
    echo.
)

if not exist "pet_assets\front.png" (
    echo [X] Missing sprite: pet_assets\front.png
    echo     See README section "素材与授权" for how to prepare assets.
    echo.
    exit /b 1
)

echo [OK] Starting pet...
rem 用 pythonw 无控制台启动；找不到就退回 python（会带一个控制台窗口）
where pythonw >nul 2>nul
if errorlevel 1 (
    start "WhaleMaidPet" python quota_pet.py
) else (
    start "WhaleMaidPet" pythonw quota_pet.py
)

echo [OK] Done. She should appear at the bottom-right of your screen.
echo      Run stop-pet.bat to close her, or right-click her - Quit All.
echo.
ping -n 3 127.0.0.1 >nul
exit /b 0
