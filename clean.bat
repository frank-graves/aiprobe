@echo off
setlocal enabledelayedexpansion

REM ================================================
REM  clean.bat - Elimina artefactos regenerables
REM
REM  Uso:
REM    clean.bat        Pide confirmacion antes de borrar
REM    clean.bat /y     Sin confirmacion (modo CI)
REM ================================================

REM Asegura que trabajamos en la raiz del proyecto
cd /d "%~dp0"

set "CONFIRM=1"
if /i "%~1"=="/y" set "CONFIRM=0"
if /i "%~1"=="-y" set "CONFIRM=0"

echo ==========================================
echo  Limpieza del proyecto
echo ==========================================
echo.

REM --- Aviso si hay un venv activo ---
if defined VIRTUAL_ENV (
    echo [WARN] Hay un entorno virtual activo: %VIRTUAL_ENV%
    echo        Si es el .venv del proyecto, ejecuta "deactivate" antes.
    echo.
)

call :measure
set "COUNT_BEFORE=!COUNT!"
set "SIZE_BEFORE=!SIZE!"

echo Estado actual:
echo   Archivos: !COUNT_BEFORE!
echo   Tamano:   !SIZE_BEFORE! MB
echo.

echo Se eliminaran:
echo   [Entorno]   .venv\
echo   [Caches]    .mypy_cache\  .pytest_cache\  .ruff_cache\  .hypothesis\
echo   [Bytecode]  **\__pycache__\  *.pyc  *.pyo
echo   [Build]     build\  dist\  *.egg-info\
echo   [Coverage]  .coverage  htmlcov\
echo   [Sueltos]   tree.txt
echo.

if "!CONFIRM!"=="1" (
    set /p "ANSWER=Eliminar estos elementos? [s/N]: "
    if /i not "!ANSWER!"=="s" (
        echo.
        echo Cancelado. No se ha borrado nada.
        exit /b 0
    )
    echo.
)

echo [1/5] Directorios de entorno / cache / build ...
for %%D in (.venv .mypy_cache .pytest_cache .ruff_cache .hypothesis build dist htmlcov) do (
    if exist "%%D" (
        rmdir /s /q "%%D" 2>nul
        if exist "%%D" (
            echo   [WARN] %%D  ^(en uso, no se pudo borrar^)
        ) else (
            echo   [OK]   %%D
        )
    )
)

echo [2/5] Metadatos *.egg-info ...
for /d %%D in (*.egg-info) do (
    if exist "%%D" (
        rmdir /s /q "%%D" 2>nul
        echo   [OK]   %%D
    )
)

echo [3/5] Carpetas __pycache__ ...
set /a PYC_DIRS=0
for /d /r %%D in (__pycache__) do (
    if exist "%%D" (
        rmdir /s /q "%%D" 2>nul
        set /a PYC_DIRS+=1
    )
)
echo   [OK]   !PYC_DIRS! carpetas eliminadas

echo [4/5] Restos .pyc / .pyo ...
set /a PYC_FILES=0
for /r %%F in (*.pyc *.pyo) do (
    if exist "%%F" (
        del /q "%%F" 2>nul
        set /a PYC_FILES+=1
    )
)
echo   [OK]   !PYC_FILES! archivos eliminados

echo [5/5] Archivos sueltos ...
for %%F in (tree.txt .coverage) do (
    if exist "%%F" (
        del /q "%%F" 2>nul
        echo   [OK]   %%F
    )
)

echo.
call :measure

echo ==========================================
echo  Limpieza completada
echo ==========================================
echo   Archivos: !COUNT_BEFORE! -^> !COUNT!
echo   Tamano:   !SIZE_BEFORE! MB -^> !SIZE! MB
echo.
echo Siguiente paso: ejecutar setup.bat
echo ==========================================
exit /b 0

REM ================================================
REM  :measure - Calcula COUNT (num archivos) y
REM             SIZE (MB) del proyecto, excluyendo
REM             solo la carpeta .git.
REM ================================================
:measure
set "COUNT=0"
set "SIZE=0.00"
set "TMPFILE=%TEMP%\aiprobe_measure_%RANDOM%%RANDOM%.txt"
powershell -NoProfile -Command "$f = Get-ChildItem -Recurse -File -Force -ErrorAction SilentlyContinue ^| Where-Object { $_.FullName -notlike '*\.git\*' }; '{0}|{1:N2}' -f $f.Count, (($f ^| Measure-Object Length -Sum).Sum / 1MB)" > "%TMPFILE%" 2>nul
for /f "delims=| tokens=1,2" %%A in ('type "%TMPFILE%" 2^>nul') do (
    set "COUNT=%%A"
    set "SIZE=%%B"
)
del "%TMPFILE%" 2>nul
exit /b 0
