@echo off
setlocal
chcp 65001 >nul 2>&1

REM Переход в каталог с проектом
cd /d "%~dp0"

REM Проверка наличия Python
echo Проверка Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python не найден! Пожалуйста, установите Python 3.x
    pause
    exit /b 1
)

REM Проверка и создание виртуального окружения
if not exist ".venv" (
    echo Создание виртуального окружения...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo Не удалось создать venv.
        pause
        exit /b 1
    )
)

REM Активация виртуального окружения
call ".venv\Scripts\activate.bat"
if %errorlevel% neq 0 (
    echo Не удалось активировать venv.
    pause
    exit /b 1
)

REM Установка зависимостей (только если requirements изменились)
if exist "config\requirements.txt" (
    echo Проверка зависимостей...
    python -m pip install -q -r config\requirements.txt
)

REM Запуск приложения
echo Запуск приложения...
python src\app.py

pause
