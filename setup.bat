@echo off
setlocal

echo ==========================================
echo  Configurando entorno de desarrollo
echo ==========================================
echo.

REM --- 1) Comprobar que Python existe ---
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python no esta en el PATH.
    echo Instala Python 3.12+ desde https://www.python.org/downloads/
    exit /b 1
)

REM --- 2) Crear el venv ---
if exist .venv (
    echo [INFO] .venv ya existe, se omite su creacion.
) else (
    echo [1/3] Creando entorno virtual en .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el venv.
        exit /b 1
    )
)

REM --- 3) Actualizar pip e instalar ---
call .venv\Scripts\activate.bat

echo [2/3] Actualizando pip ...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] Fallo al actualizar pip.
    exit /b 1
)

echo [3/3] Instalando el proyecto con extras [dev] ...
python -m pip install -e ".[dev]"
if errorlevel 1 (
    echo [ERROR] Fallo la instalacion de dependencias.
    exit /b 1
)

echo.
echo ==========================================
echo  Listo.
echo  Activa el entorno con:
echo      .venv\Scripts\activate
echo ==========================================
endlocal
