@echo off
setlocal

cd /d "%~dp0"

echo Checking for Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found!
    echo Attempting to install Python via winget...
    winget --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo Winget not found. Please install Python manually.
        if not defined CI pause
        exit /b 1
    )
    
    winget install -e --id Python.Python.3.12
    if %errorlevel% neq 0 (
        echo Failed to install Python. Please install Python manually and try again.
        if not defined CI pause
        exit /b 1
    )
    
    echo Python installed.
    echo NOTE: You might need to restart this console or your PC if the 'python' command is not recognized immediately.
    echo Trying to proceed...
    timeout /t 3
)

REM Verify python again or proceed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    REM Try to look in standard installation path for current user (Local AppData) as fallback?
    REM Too complex. Just error out if still not found.
    echo Python command not available yet. Please restart the script/console.
    if not defined CI pause
    exit /b 1
)

echo Checking for virtual environment...
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo Failed to create venv.
        if not defined CI pause
        exit /b 1
    )
)

echo Activating virtual environment...
call ".venv\Scripts\activate.bat"
if %errorlevel% neq 0 (
    echo Failed to activate venv.
    if not defined CI pause
    exit /b 1
)

echo Installing dependencies...
python -m pip install --upgrade pip
if exist "requirements.txt" (
    python -m pip install -r requirements.txt
) else (
    echo requirements.txt not found!
    if not defined CI pause
    exit /b 1
)

echo Installing PyInstaller...
python -m pip install --upgrade pyinstaller

echo Cleaning previous builds...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del /q *.spec 2>nul

echo Building EXE...
pyinstaller ^
  --noconfirm ^
  --onedir ^
  --noconsole ^
  --name GoogleToYandexWeb ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --add-data "calibration.json;." ^
  app.py

if errorlevel 1 (
    echo Build failed!
    pause
    exit /b 1
)

echo.
echo ===================================================
echo Done! Output: %~dp0dist\GoogleToYandexWeb\GoogleToYandexWeb.exe
echo ===================================================
pause
