$ErrorActionPreference = "Stop"

function Fail($msg) { Write-Host "[ERROR] $msg" -ForegroundColor Red; exit 1 }

# 1) Comprobar Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Fail "Python no está en el PATH. Instala Python 3.12+ desde https://www.python.org/downloads/"
}

# 2) Crear venv si no existe
if (-not (Test-Path ".venv")) {
    Write-Host "[1/3] Creando entorno virtual en .venv ..."
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { Fail "No se pudo crear el venv." }
} else {
    Write-Host "[INFO] .venv ya existe, se omite su creación."
}

$python = ".\.venv\Scripts\python.exe"

# 3) Actualizar pip
Write-Host "[2/3] Actualizando pip ..."
& $python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { Fail "Fallo al actualizar pip." }

# 4) Instalar paquete + extras dev
Write-Host "[3/3] Instalando el proyecto con extras [dev] ..."
& $python -m pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) { Fail "Fallo la instalación de dependencias." }

Write-Host "`nListo. Activa con: .\.venv\Scripts\Activate.ps1" -ForegroundColor Green
