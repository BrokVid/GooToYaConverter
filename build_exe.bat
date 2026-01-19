@echo off
setlocal

REM Build GoogleToYandexWeb as Windows exe (onedir) using the root .venv
cd /d "%~dp0"

REM Activate venv from project root
call "..\.venv\Scripts\activate.bat"

python -m pip install --upgrade pip
python -m pip install --upgrade pyinstaller

REM Clean previous builds
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del /q *.spec 2>nul

REM Build: keep data files next to exe (onedir) for predictable paths, без консоли
pyinstaller ^
  --noconfirm ^
  --onedir ^
  --noconsole ^
  --name GoogleToYandexWeb ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --add-data "calibration.json;." ^
  app.py

echo.
echo Done. Output: %~dp0dist\GoogleToYandexWeb\GoogleToYandexWeb.exe
pause

