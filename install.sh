#!/bin/bash

echo ""
echo "⛏  PoLM Easy Miner — Instalação"
echo "================================"
echo ""

if ! command -v wget &>/dev/null && ! command -v curl &>/dev/null; then
    echo "[!] Instale wget: sudo apt install wget"
    exit 1
fi

RAM_KB=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}' || echo 0)
RAM_GB=$((${RAM_KB:-0} / 1024 / 1024))
if [ "$RAM_GB" -lt 4 ]; then
    echo "[!] Atencao: menos de 4GB de RAM. Minimo recomendado: 8GB."
fi

INSTALL_DIR="$HOME/polm-miner"
mkdir -p 2>/dev/null ||true; mkdir -p "$INSTALL_DIR"
echo "[*] Baixando PoLM Miner v3.0.1..."
wget -q --show-progress -O "$INSTALL_DIR/polm-miner" \
    https://github.com/proof-of-legacy/Proof-of-Legacy-Memory/releases/download/v3.0.1/polm-miner-linux-amd64
chmod +x "$INSTALL_DIR/polm-miner"
echo "[✓] Instalado em $INSTALL_DIR/polm-miner"
echo ""
echo "Iniciando minerador..."
echo ""
exec "$INSTALL_DIR/polm-miner"
