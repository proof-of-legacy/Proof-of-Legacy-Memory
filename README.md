# ⛏ PoLM — Proof of Legacy Memory

> The first RAM-latency-bound Proof-of-Work. Mine with any RAM. DDR2, DDR3, DDR4, DDR5 — every generation mines. Score = 1/latency. Physics can't be faked.

[![Mainnet](https://img.shields.io/badge/mainnet-live-brightgreen)](https://polm.com.br/explorer)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Twitter](https://img.shields.io/badge/twitter-@polmram-1DA1F2)](https://x.com/polmram)
[![Miner](https://img.shields.io/badge/miner-v1.5.19-orange)](https://polm.com.br)

---

## ⛏️ Como Minerar (Linux)

**Não precisa compilar nada. Só baixar e rodar.**

### Instalação em 3 comandos
```bash
wget https://github.com/proof-of-legacy/Proof-of-Legacy-Memory/releases/download/v3.0.0/polm-miner-linux-amd64
chmod +x polm-miner-linux-amd64
./polm-miner-linux-amd64 --wallet SUA_CARTEIRA_POLYGON
```

**Requisitos:** Ubuntu/Debian x64 · 8GB+ RAM · Sem GPU

### Instalação automática (script)
```bash
wget -qO- https://raw.githubusercontent.com/proof-of-legacy/Proof-of-Legacy-Memory/main/install.sh | bash
```

### Mineração via systemd (boot automático)
O script `install.sh` oferece configuração automática como serviço.

## 🟢 Mainnet Live

| | |
|---|---|
| 🌐 Website | https://polm.com.br |
| 🔍 Explorer | https://polm.com.br/explorer |
| 💰 Claim POLM | https://polm.com.br/claim |
| 🗺 Roadmap | https://polm.com.br/roadmap |
| ⚙️ Node API | https://polm.com.br/api/ |

---

## ⚡ Quick Start — Mining

### 🪟 Windows — PowerShell

```powershell
# Step 1: Install Python 3.11
winget install Python.Python.3.11

# Step 2: Download the miner
mkdir $env:USERPROFILE\polm
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/proof-of-legacy/Proof-of-Legacy-Memory/main/polm_miner_cli.py" -OutFile "$env:USERPROFILE\polm\miner.py"

# Step 3: Enter the folder (REQUIRED)
cd $env:USERPROFILE\polm

# Step 4: Run
python miner.py
```

> ⚠️ Always `cd` into the folder before running.

### 🐧 Linux / macOS — Terminal

```bash
curl -O https://raw.githubusercontent.com/proof-of-legacy/Proof-of-Legacy-Memory/main/polm_miner_cli.py
python3 polm_miner_cli.py
```

The miner auto-updates on every run. On first run: generates 12-word BIP-39 wallet, registers Polygon wallet, starts mining immediately.

---

## ⚡ Native C Miner — Proof of Real Memory

The Python miner measures **~900ns** for DDR4 — but that's interpreter overhead, not DRAM latency. The native C miner implements **PoRM (Proof of Real Memory)**: a cryptographic proof that your physical RAM was actually accessed.

```
Python miner:  ~900ns  ← interpreter overhead
C miner:       ~76ns   ← real DRAM latency (DDR4)
```

Blocks mined with the C miner appear with **⚡** in the explorer.

### How PoRM Works

1. Generate a 256MB DAG from the epoch seed
2. Walk 1,000 random positions (4KB stride — cache miss guaranteed)
3. Collect `merge_value` = 8,000 bytes read from physical DRAM
4. Submit proof to the network for verification
5. The network independently recalculates the entire path

**Why it can't be faked:** the verifier recalculates all 1,000 steps and compares the result byte-by-byte. You must read physical memory.

### Build (Linux x86-64)

```bash
# Dependencies
sudo apt install gcc libssl-dev libcurl4-openssl-dev

# Clone
git clone https://github.com/proof-of-legacy/Proof-of-Legacy-Memory
cd Proof-of-Legacy-Memory/miner

# Build BLAKE3
git clone https://github.com/BLAKE3-team/BLAKE3.git --depth=1
gcc -O3 -c BLAKE3/c/blake3.c BLAKE3/c/blake3_dispatch.c \
    BLAKE3/c/blake3_portable.c \
    BLAKE3/c/blake3_avx2_x86-64_unix.S \
    BLAKE3/c/blake3_avx512_x86-64_unix.S \
    BLAKE3/c/blake3_sse41_x86-64_unix.S \
    BLAKE3/c/blake3_sse2_x86-64_unix.S \
    -I BLAKE3/c/
ar rcs libblake3.a blake3.o blake3_dispatch.o blake3_portable.o \
    blake3_avx2_x86-64_unix.o blake3_avx512_x86-64_unix.o \
    blake3_sse41_x86-64_unix.o blake3_sse2_x86-64_unix.o

# Build miner
gcc -O3 -o polm_miner polm_miner_v2.c polm_posma.c \
    -I BLAKE3/c libblake3.a \
    -lssl -lcrypto -lcurl -lm
```

### Run

```bash
# Optional: enable Huge Pages for lower latency
sudo sysctl -w vm.nr_hugepages=256

# Mine
./polm_miner YOUR_POLM_ADDRESS https://polm.com.br/api
```

**Example output:**
```
  TSC: 2.496 GHz (calibrado)
  Huge Pages: ativado (TLB otimizado)
  Building DAG (seed: polm:0:... salt: epoch_0_...)  done
  Mining #38200  diff=2  reward=50.00 POLM
  Block found! nonce=38442 hash=00efb234... lat=76.8ns
  ACCEPTED! Blocks=1 Earned=50.0 POLM
```

---

## 🖥️ Run a Full Node

Anyone can run a PoLM full node. No permission needed.

**Requirements:** Python 3.10+ · 4 GB RAM · ~500 MB disk · Port 6060 open

```bash
git clone https://github.com/proof-of-legacy/Proof-of-Legacy-Memory.git
cd Proof-of-Legacy-Memory
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 polm.py node 6060
```

Your node automatically connects to the network, downloads the blockchain and joins P2P. No configuration needed.

---

## 🔷 POLM on Polygon

Mine natively → Oracle registers blocks → Claim your ERC-20 POLM on Polygon.

```
Contract:  0x79175931C54c9765E5846229a0eB118ef24fdE55
Network:   Polygon Mainnet (Chain ID 137)
Verified:  Sourcify ✅  Blockscout ✅
Claim fee: 0.5 MATIC
```

[PolygonScan](https://polygonscan.com/token/0x79175931C54c9765E5846229a0eB118ef24fdE55) · [Claim POLM](https://polm.com.br/claim)

---

## 🧠 Algorithm

```
score = 1 / latency_ns
```

No boost multiplier. No penalty. Pure physics.

- **Slower RAM** → higher latency → higher score per step → valid block
- **Faster RAM** → lower latency → more nonces per second → valid block

### Any RAM Mines

| Generation | Avg Latency | Profile |
|-----------|------------|---------|
| DDR2 | ~3500–8000 ns | High latency → high score/step ✅ |
| DDR3 | ~1500–4000 ns | Balanced latency profile ✅ |
| DDR4 | ~900–1900 ns | More nonces per second ✅ |
| DDR5 | ~500–900 ns | Highest nonce throughput ✅ |

### Why ASIC-Resistant?

No ASIC can accelerate the physical latency of DRAM. The access time is a property of the hardware — not the computation. An ASIC mining PoLM would need to be a RAM module.

---

## 📊 Tokenomics

| Parameter | Value |
|-----------|-------|
| Symbol | POLM |
| Max supply | 210,000,000 |
| Block reward (Epoch 0) | 50 POLM |
| Block time | 2 minutes |
| Halving interval | 100,000 blocks (~138 days) |
| Hash algorithm | SHA3-256 |
| Signatures | ECDSA secp256k1 |
| HD wallet | BIP-39 / BIP-44 |
| Pre-mine / ICO | None |
| Founder allocation | 10,500,000 POLM (5%) · locked 5 years |

### Epoch Schedule

| Epoch | Blocks | DAG | Min RAM | Reward |
|-------|--------|-----|---------|--------|
| **0 ← NOW** | 0–100k | 256 MB | 4 GB | 50 POLM |
| 1 | 100k–200k | 512 MB | 8 GB | 25 POLM |
| 2 | 200k–300k | 1 GB | 16 GB | 12.5 POLM |
| 3 | 300k–400k | 2 GB | 32 GB | 6.25 POLM |
| 4 | 400k–500k | 4 GB | 64 GB | 3.125 POLM |
| 5 | 500k–600k | 8 GB | 128 GB | 1.5625 POLM |
| 6 | 600k–700k | 16 GB | 256 GB | 0.781 POLM |
| 7 ⚡ | 700k–800k | 32 GB | 512 GB | 0.390 POLM |
| 8+ 🏭 | 800k+ | 64 GB+ | 2 TB+ | 0.195 POLM |

> **Epoch 0 is the most accessible window** — any PC with 4 GB+ RAM mines today.

---

## 🛡 Security

| Attack | Defense |
|--------|---------|
| ASIC | 256 MB+ DAG — DRAM physics can't be miniaturized |
| GPU | GDDR latency ≥ DDR latency — no advantage |
| Cache exploit | Latency validation rejects synthetic values |
| Fake latency | PoRM cryptographic proof required for ⚡ blocks |
| Oracle fraud | Cryptographic signature required on every PoRM block |
| Rug pull | Founder locked 5 years — smart contract enforced |
| Sybil attack | 1 IP = 1 active miner enforced at network level |

---

## 📁 Repository

```
polm.py                ← Full node (P2P + API + consensus)
polm_miner_cli.py      ← Python CLI miner · auto-update · v1.5.19
polm_miner_gui.py      ← GUI miner (Windows / Linux / macOS)
polm_explorer.py       ← Blockchain explorer
polm_bip39.py          ← BIP-39/BIP-32 HD wallet
polm_bridge_oracle.py  ← Polygon bridge oracle
polm_wallet.py         ← Web wallet UI
temporal_sync.py       ← Temporal sync validator
miner/                 ← Native C miner (PoRM ⚡)
  polm_miner_v2.c      ← Main miner
  polm_posma.c/.h      ← PoSMA library
requirements.txt       ← flask cryptography mnemonic requests
```

---

## 🌐 REST API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Node status + summary |
| `/getwork` | GET | Mining job |
| `/submit` | POST | Submit mined block |
| `/register_evm` | POST | Register Polygon wallet |
| `/chain` | GET | Block list |
| `/block/<h>` | GET | Block details |
| `/balance/<addr>` | GET | Address balance |
| `/miners` | GET | Leaderboard with CPU info |
| `/peers` | GET | Connected P2P peers |
| `/connected_miners` | GET | Active miners |

---

## 🗺 Roadmap

- [x] v1.0 — Algorithm designed and validated
- [x] v2.0 — Pure latency consensus · any RAM mines
- [x] Mainnet live — polm.com.br
- [x] Polygon ERC-20 contract — verified + founder lock 5 years
- [x] Oracle — auto-sustaining bridge
- [x] Claim page — polm.com.br/claim
- [x] GUI miner — Windows / Linux / macOS
- [x] CLI miner — no dependencies · auto-update
- [x] CPU auto-detection in explorer
- [x] Full node published
- [x] P2P network — DNS seeds + peer discovery
- [x] **Native C miner — Proof of Real Memory (PoRM) ⚡**
- [x] **BLAKE3 path hash — 3.3x faster than SHA3**
- [x] **Cryptographic oracle signatures**
- [ ] DEX listing — QuickSwap (Polygon)
- [ ] Mining pool
- [ ] CoinGecko / CoinMarketCap listing
- [ ] CEX listing
- [ ] RAM mining board ecosystem (Epoch 7)

---

## 👥 Community

| | |
|---|---|
| 🐦 Project | [@polmram](https://x.com/polmram) |
| 👤 Founder | [@aluisiofer](https://x.com/aluisiofer) |
| 📱 Telegram | [t.me/polm2026](https://t.me/polm2026) |
| 🗣 Bitcointalk | [topic=5579305](https://bitcointalk.org/index.php?topic=5579305) |
| ⚙️ GitHub | [proof-of-legacy](https://github.com/proof-of-legacy) |
| 📧 Contact | contact@polm.com.br |

---

*PoLM is experimental software. Not financial advice. MIT License · © 2026 Aluísio Fernandes (Aluminium)*

*Proof of Memory. Qualquer RAM minera.*
