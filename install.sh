#!/bin/bash
echo ""
echo "⛏  PoLM Miner — Instalação"
echo "==========================="
echo ""

# Verifica Python
if ! command -v python3 &>/dev/null; then
    echo "[!] Python3 não encontrado. Instale com: sudo apt install python3"
    exit 1
fi

PYTHON_VER=$(python3 -c 'import sys; print(sys.version_info.minor)')
if [ "$PYTHON_VER" -lt 8 ]; then
    echo "[!] Python 3.8+ necessário. Versão encontrada: 3.$PYTHON_VER"
    exit 1
fi

# Verifica RAM
RAM_KB=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}' || echo 0)
RAM_GB=$((${RAM_KB:-0} / 1024 / 1024))
if [ "$RAM_GB" -lt 4 ]; then
    echo "[!] Atenção: menos de 4GB de RAM detectados. Mínimo recomendado: 4GB."
fi

# Instala dependências Python
echo "[*] Instalando dependências..."
pip3 install requests mnemonic --quiet 2>/dev/null || true

# Cria pasta e baixa miner
INSTALL_DIR="$HOME/polm-miner"
mkdir -p "$INSTALL_DIR"

echo "[*] Baixando PoLM Miner CLI..."
if command -v wget &>/dev/null; then
    wget -q -O "$INSTALL_DIR/miner.py" \
        https://raw.githubusercontent.com/proof-of-legacy/Proof-of-Legacy-Memory/main/polm_miner_cli.py
else
    curl -s -o "$INSTALL_DIR/miner.py" \
        https://raw.githubusercontent.com/proof-of-legacy/Proof-of-Legacy-Memory/main/polm_miner_cli.py
fi

echo "[✓] Instalado em $INSTALL_DIR/miner.py"
echo ""

# Opção de instalar como serviço systemd
read -p "Instalar como serviço (boot automático)? [s/N]: " INSTALL_SERVICE
if [[ "$INSTALL_SERVICE" =~ ^[Ss]$ ]]; then
    read -p "Endereço POLM para minerar: " POLM_ADDR
    if [ -n "$POLM_ADDR" ]; then
        cat > /tmp/polm-miner.service << EOF
[Unit]
Description=PoLM Miner
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=python3 $INSTALL_DIR/miner.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF
        sudo mv /tmp/polm-miner.service /etc/systemd/system/
        sudo systemctl daemon-reload
        sudo systemctl enable polm-miner
        sudo systemctl start polm-miner
        echo "[✓] Serviço instalado e iniciado!"
        echo "    Ver logs: journalctl -u polm-miner -f"
        exit 0
    fi
fi

echo "Iniciando minerador..."
echo ""
cd "$INSTALL_DIR"
exec python3 miner.py
