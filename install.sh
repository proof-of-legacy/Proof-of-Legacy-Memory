#!/bin/bash
set -e

echo ""
echo "⛏  PoLM Easy Miner — Instalação"
echo "================================"
echo ""

# Verificar dependências
if ! command -v wget &>/dev/null && ! command -v curl &>/dev/null; then
    echo "[!] Instale wget ou curl primeiro: sudo apt install wget"
    exit 1
fi

# Verificar RAM
RAM_KB=$(grep MemTotal /proc/meminfo | awk "{print $2}")
RAM_GB=$((RAM_KB / 1024 / 1024))
if [ "$RAM_GB" -lt 4 ] 2>/dev/null; then
    echo "[!] Atencao: menos de 4GB de RAM. Minimo recomendado: 8GB."
fi

# Baixar binário
INSTALL_DIR="$HOME/polm-miner"
mkdir -p "$INSTALL_DIR"
echo "[*] Baixando PoLM Miner v3.0.1..."
wget -q --show-progress -O "$INSTALL_DIR/polm-miner" \
    https://github.com/proof-of-legacy/Proof-of-Legacy-Memory/releases/latest/download/polm-miner-linux-amd64
chmod +x "$INSTALL_DIR/polm-miner"
echo "[✓] Binário instalado em $INSTALL_DIR/polm-miner"

# Pedir carteira
echo ""
echo "Digite seu endereço de carteira Polygon (MetaMask):"
echo "Exemplo: 0x71C7656EC7ab88b098defB751B7401B5f6d8976F"
read -p "Carteira: " WALLET

if [ -z "$WALLET" ]; then
    echo "[!] Carteira não informada. Execute manualmente:"
    echo "    $INSTALL_DIR/polm-miner --wallet SEU_ENDERECO"
    exit 1
fi

# Criar script de início
cat > "$INSTALL_DIR/start.sh" << STARTEOF
#!/bin/bash
$INSTALL_DIR/polm-miner --wallet $WALLET
STARTEOF
chmod +x "$INSTALL_DIR/start.sh"

echo ""
echo "[✓] Configurado para carteira: $WALLET"
echo ""
echo "Para minerar agora:"
echo "  $INSTALL_DIR/start.sh"
echo ""

# Oferecer systemd
read -p "Deseja instalar como serviço (iniciar no boot)? [s/N]: " SYSTEMD
if [[ "$SYSTEMD" =~ ^[Ss]$ ]]; then
    sudo tee /etc/systemd/system/polm-miner.service > /dev/null << SVCEOF
[Unit]
Description=PoLM Miner v3.0.1 — Proof of Real Memory
After=network.target

[Service]
Type=simple
User=$USER
ExecStart=$INSTALL_DIR/polm-miner --wallet $WALLET
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
SVCEOF
    sudo systemctl daemon-reload
    sudo systemctl enable polm-miner
    sudo systemctl start polm-miner
    echo "[✓] Serviço instalado e iniciado!"
    echo "    Ver logs: journalctl -u polm-miner -f"
else
    echo "Para rodar manualmente: $INSTALL_DIR/start.sh"
fi

echo ""
echo "Explorer: https://polm.com.br/explorer"
echo "GitHub:   https://github.com/proof-of-legacy/Proof-of-Legacy-Memory"
echo ""
