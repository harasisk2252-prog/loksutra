param([switch]$SetupOnly)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    Write-Host 'Creating the local Python environment...'
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv (Join-Path $PSScriptRoot '.venv')
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv (Join-Path $PSScriptRoot '.venv')
    } else { throw 'Install Python 3 with Tcl/Tk support, then try again.' }
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
}
& $python -B -c "import fastapi,uvicorn,httpx,dotenv,pydantic,python_multipart"
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Installing required packages into the local environment...'
    & $python -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check the internet connection and retry.' }
}
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot '.env'))) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot '.env.example') -Destination (Join-Path $PSScriptRoot '.env')
}
& $python -B -c "from dotenv import dotenv_values; from owner_auth import valid_hash; v=dotenv_values('.env',encoding='utf-8-sig'); exit(0 if valid_hash(v.get('OWNER_PASSWORD_HASH','')) else 2)"
$ownerReady = $LASTEXITCODE -eq 0
if ($SetupOnly -or -not $ownerReady) {
    Write-Host 'Opening private password setup. Enter your password only in that window.'
    & $python -B (Join-Path $PSScriptRoot 'setup_owner.py') --gui
    if ($LASTEXITCODE -ne 0) { Write-Host 'Password setup cancelled or incomplete. No server started.'; exit 1 }
}
if ($SetupOnly) { exit 0 }
& $python -B -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',8000)); s.close()"
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Port 8000 is already in use. If LokSutra is running, open http://127.0.0.1:8000 . Otherwise close the other server and retry.'
    exit 1
}
Write-Host 'Open http://127.0.0.1:8000 . Keep this window open. Stop with Ctrl+C.'
& $python -m uvicorn main:app --app-dir $PSScriptRoot --host 127.0.0.1 --port 8000 --no-proxy-headers
