@echo off
setlocal
chcp 65001 >nul 2>&1

REM Переходим в корневую папку проекта
cd /d "%~dp0"

echo Проверка Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python не найден!
    echo Попытка установить Python через winget...
    winget --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo Winget не найден. Пожалуйста, установите Python вручную.
        if not defined CI pause
        exit /b 1
    )
    
    winget install -e --id Python.Python.3.12
    if %errorlevel% neq 0 (
        echo Не удалось установить Python. Пожалуйста, установите его вручную.
        if not defined CI pause
        exit /b 1
    )
    
    echo Python установлен.
    echo ПРИМЕЧАНИЕ: Возможно потребуется перезапустить консоль или ПК, если команда 'python' не распознаётся сразу.
    echo Продолжаем...
    timeout /t 3
)

REM Повторная проверка Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Команда Python всё ещё недоступна. Перезапустите скрипт или консоль.
    if not defined CI pause
    exit /b 1
)

echo Проверка виртуального окружения...
if not exist ".venv" (
    echo Создание виртуального окружения...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo Не удалось создать venv.
        if not defined CI pause
        exit /b 1
    )
)

echo Активация виртуального окружения...
call ".venv\Scripts\activate.bat"
if %errorlevel% neq 0 (
    echo Не удалось активировать venv.
    if not defined CI pause
    exit /b 1
)

echo Установка зависимостей...
python -m pip install --upgrade pip
if exist "config\requirements.txt" (
    python -m pip install -r config\requirements.txt
) else (
    echo config\requirements.txt не найден!
    if not defined CI pause
    exit /b 1
)

echo Установка PyInstaller...
python -m pip install --upgrade pyinstaller

echo Очистка предыдущих сборок...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del /q *.spec 2>nul

echo Сборка EXE (один файл)...
pyinstaller ^
  --noconfirm ^
  --onefile ^
  --noconsole ^
  --name GoogleToYandexWeb ^
  --add-data "src\templates;templates" ^
  --add-data "src\static;static" ^
  src\app.py

if errorlevel 1 (
    echo Сборка не удалась!
    pause
    exit /b 1
)

echo.
echo ===================================================
echo Готово! Файл: %~dp0dist\GoogleToYandexWeb.exe
echo ===================================================
pause
