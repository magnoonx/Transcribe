@echo off
setlocal enabledelayedexpansion
title Transcribe Portable Launcher
echo ===================================================
echo   Iniciando Subtitulador Portable (Antigravity/Python)
echo ===================================================
echo.

cd /d "%~dp0"

set "PYTHON_CMD=python"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_CMD=.venv\Scripts\python.exe"
    echo Usando entorno virtual local 
) else (
    echo Usando Python del sistema...
)

echo Verificando librerias...
!PYTHON_CMD! -c "import faster_whisper" >nul 2>&1
if !errorlevel! neq 0 (
    echo.
    echo [!] No se encontro faster_whisper. Preparing entorno...
    !PYTHON_CMD! -m pip --version >nul 2>&1
    if !errorlevel! neq 0 (
        echo [!] Instalando pip en el entorno virtual...
        !PYTHON_CMD! -m ensurepip --default-pip
    )
    echo [!] Instalando librerias desde requirements.txt...
    echo.
    !PYTHON_CMD! -m pip install -r requirements.txt
    echo.
)

echo Iniciando generar_srt.py...
!PYTHON_CMD! generar_srt.py

pause
