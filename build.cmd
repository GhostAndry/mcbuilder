@echo off
REM Build portable executable for Windows.
SETLOCAL ENABLEDELAYEDEXPANSION

SET "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

SET "VENV_DIR=.venv-build"
IF NOT DEFINED PYTHON SET "PYTHON=python"

IF NOT EXIST "%VENV_DIR%" (
    echo ^>^> Creating virtualenv...
    "%PYTHON%" -m venv "%VENV_DIR%"
    IF ERRORLEVEL 1 EXIT /B 1
)

"%VENV_DIR%\Scripts\python.exe" -c "import tkinter; assert tkinter.TkVersion >= 8.6"
IF ERRORLEVEL 1 EXIT /B 1

echo ^>^> Installing dependencies...
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip --quiet
IF ERRORLEVEL 1 EXIT /B 1
"%VENV_DIR%\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller --quiet
IF ERRORLEVEL 1 EXIT /B 1

echo ^>^> Building executable (single file, no console)...
"%VENV_DIR%\Scripts\python.exe" -m PyInstaller ^
    --name "MCBuilder" ^
    --onefile ^
    --noconsole ^
    --noconfirm ^
    --clean ^
    --add-data "mcbuilder/templates;mcbuilder/templates" ^
    --add-data "mcbuilder/assets;mcbuilder/assets" ^
    --collect-all customtkinter ^
    --collect-all tkinter ^
    --paths . ^
    --hidden-import customtkinter ^
    --hidden-import tkinter ^
    --hidden-import tkinter.ttk ^
    --hidden-import tkinter.filedialog ^
    --hidden-import tkinter.messagebox ^
    --hidden-import mcbuilder ^
    run.py
IF ERRORLEVEL 1 EXIT /B 1

echo.
echo Done. Binary: dist\MCBuilder.exe
echo   Run with: dist\MCBuilder.exe

ENDLOCAL
