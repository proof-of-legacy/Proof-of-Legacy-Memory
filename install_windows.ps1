# PoLM Miner — Windows Installer
# Execute: powershell -ExecutionPolicy Bypass -File install_windows.ps1

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  PoLM Miner — Proof of Legacy Memory" -ForegroundColor Cyan
Write-Host "  Windows Installer" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# 1. Instala Python se necessario
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[1/4] Instalando Python..." -ForegroundColor Yellow
    winget install Python.Python.3.11 --silent --accept-package-agreements
    $env:PATH += ";$env:LOCALAPPDATA\Programs\Python\Python311"
} else {
    Write-Host "[1/4] Python ja instalado." -ForegroundColor Green
}

# 2. Cria pasta do miner
$POLM_DIR = "$env:USERPROFILE\polm"
New-Item -ItemType Directory -Force -Path $POLM_DIR | Out-Null
Write-Host "[2/4] Pasta criada: $POLM_DIR" -ForegroundColor Green

# 3. Baixa o miner
Write-Host "[3/4] Baixando miner..." -ForegroundColor Yellow
$url = "https://raw.githubusercontent.com/proof-of-legacy/Proof-of-Legacy-Memory/main/polm_miner_cli.py"
Invoke-WebRequest -Uri $url -OutFile "$POLM_DIR\miner.py"
Write-Host "[3/4] Miner baixado." -ForegroundColor Green

# 4. Instala dependencias
Write-Host "[4/4] Instalando dependencias..." -ForegroundColor Yellow
Set-Location $POLM_DIR
python -m pip install requests --quiet

# Cria atalho no Desktop
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\PoLM Miner.lnk")
$Shortcut.TargetPath = "powershell.exe"
$Shortcut.Arguments = "-ExecutionPolicy Bypass -Command `"cd '$POLM_DIR'; python miner.py`""
$Shortcut.WorkingDirectory = $POLM_DIR
$Shortcut.IconLocation = "powershell.exe,0"
$Shortcut.Save()

Write-Host "" 
Write-Host "==================================================" -ForegroundColor Green
Write-Host "  Instalacao concluida!" -ForegroundColor Green
Write-Host "  Atalho criado no Desktop: 'PoLM Miner'" -ForegroundColor Green
Write-Host "  Ou execute manualmente:" -ForegroundColor Green
Write-Host "    cd $POLM_DIR" -ForegroundColor White
Write-Host "    python miner.py" -ForegroundColor White
Write-Host "==================================================" -ForegroundColor Green

# Pergunta se quer minerar agora
$resp = Read-Host "Iniciar mineracao agora? (S/N)"
if ($resp -eq "S" -or $resp -eq "s") {
    Set-Location $POLM_DIR
    python miner.py
}
