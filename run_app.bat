@echo off
REM Переход в каталог с приложением
cd /d "%~dp0"

REM Активация виртуального окружения из корня проекта
call ".\.venv\Scripts\activate.bat"

REM Запуск приложения во включённом venv
python app.py

pause
