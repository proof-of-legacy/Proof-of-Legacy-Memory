#!/bin/bash
# PoLM — Network Deploy Script
# Instala e configura PoLM em todos os PCs da rede local
# Uso: ./scripts/deploy_network.sh

set -e

NODE_IP="192.168.0.103"
NODE_PORT="6060"
REPO="https://github.com/proof-of-legacy/Proof-of-Legacy-Memory.git"
DIR="$HOME/Proof-of-Legacy-Memory"

# ── cores para output ─────────────────────────
GREEN='\033[0;32m'; CYAN='\033[0;36m'
YELLOW='\033[1;33m'; NC='\033[0m'

log()  { echo -e "${CYAN}[deploy]${NC} $1"; }
ok()   { echo -e "${GREEN}[ok]${NC} $1"; }
warn() { echo -e "${YELLOW}[warn]${NC} $1"; }

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║     PoLM — Network Deploy               ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── instalar dependências ─────────────────────
log "Installing system dependencies..."
sudo apt update -q
sudo apt install -y python3 python3-venv python3-pip git curl -q
ok "System dependencies installed"

# ── clonar / atualizar repo ───────────────────
log "Setting up repository..."
if [ -d "$DIR/.git" ]; then
    cd "$DIR" && git pull origin main
    ok "Repository updated"
else
    git clone "$REPO" "$DIR"
    ok "Repository cloned"
fi
cd "$DIR"

# ── corrigir bug conhecido ────────────────────
sed -i 's/NETWORK_MAGIC.*=.*b"\\xPO\\xLM"/NETWORK_MAGIC = b"POLM"/' polm.py 2>/dev/null || true

# ── ambiente virtual ──────────────────────────
log "Creating Python virtual environment..."
python3 -m venv venv
venv/bin/pip install --upgrade pip -q
venv/bin/pip install flask -q
ok "Virtual environment ready"

# ── detectar RAM ──────────────────────────────
detect_ram() {
    RAM=$(sudo dmidecode -t memory 2>/dev/null | grep -i "^\s*Type:" | \
          grep -v "Unknown\|Error\|Flash" | head -1 | awk '{print $2}')
    case "$RAM" in
        DDR2) echo "DDR2" ;; DDR3) echo "DDR3" ;;
        DDR4) echo "DDR4" ;; DDR5) echo "DDR5" ;;
        *) echo "DDR4" ;;
    esac
}

RAM=$(detect_ram)
THREADS=$(nproc)
MY_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  Hardware detected:                     ║"
printf "║  RAM     : %-30s║\n" "$RAM"
printf "║  Threads : %-30s║\n" "$THREADS"
printf "║  My IP   : %-30s║\n" "$MY_IP"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "To start the CENTRAL NODE (run only on one machine):"
echo "  cd $DIR && venv/bin/python3 polm.py node"
echo ""
echo "To start MINING:"
echo "  cd $DIR && venv/bin/python3 polm.py miner $NODE_IP YOUR_ADDRESS $RAM"
echo ""
