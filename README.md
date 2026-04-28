# ⛏ PoLM — Proof of Legacy Memory

> The first RAM-latency-bound Proof-of-Work. Mine with any RAM. DDR2, DDR3, DDR4, DDR5 — every generation mines.

[![Mainnet](https://img.shields.io/badge/Mainnet-Live-brightgreen)](https://polm.com.br)
[![License](https://img.shields.io/badge/License-MIT-blue)](LICENSE)
[![Twitter](https://img.shields.io/badge/Twitter-@polmram-1DA1F2)](https://x.com/polmram)
[![Telegram](https://img.shields.io/badge/Telegram-polm2026-blue)](https://t.me/polm2026)

---

## 🟢 Mainnet Live

| | |
|--|--|
| 🌐 Website | https://polm.com.br |
| 🔍 Explorer | https://polm.com.br/explorer |
| 💰 Claim POLM | https://polm.com.br/claim |
| 🗺 Roadmap | https://polm.com.br/roadmap |
| ⚙️ Node API | https://polm.com.br/api/ |
| 🤖 Telegram Bot | @PolmNetworkBot |

---

## ⛏️ Mine with Python — Any RAM, Any OS

No compilation needed. Just Python 3.8+.

### 🐧 Linux / macOS

```bash
curl -O https://raw.githubusercontent.com/proof-of-legacy/Proof-of-Legacy-Memory/main/polm_miner_cli.py
python3 polm_miner_cli.py
```

### 🪟 Windows

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

> ⚠️ Always `cd` into the folder before running on Windows.

### Automatic install (Linux)

```bash
wget -qO- https://raw.githubusercontent.com/proof-of-legacy/Proof-of-Legacy-Memory/main/install.sh | bash
```

The miner **auto-updates** on every run. On first run: generates a 12-word BIP-39 wallet, registers your Polygon wallet, and starts mining immediately.

**Requirements:** Python 3.8+ · 4 GB+ RAM · No GPU needed

---

## 🧠 How It Works

PoLM uses **PoSMA (Proof of Sequential Memory Access)** — a memory-hard algorithm that forces physical DRAM access on every proof:

1. Generate a **256MB DAG** from the epoch seed
2. Walk **10,000 random positions** (4112-byte stride — cache miss guaranteed)
3. Collect **merge_value** = 80KB read from physical DRAM
4. Submit proof to the network for verification
5. Network independently recalculates the entire path byte-by-byte

**Why it can't be faked:** The verifier recalculates all 10,000 steps and compares the result byte-by-byte. You must read physical memory.

**Why ASIC-resistant:** No ASIC can accelerate the physical latency of DRAM. The access time (~700–3000ns) is a property of the hardware — not computation.

```
Python miner:  ~700–1000ns  ← real DRAM latency (DDR4)
DDR3 hardware: ~2000–4000ns ← slower RAM, more latency, still mines
DDR5 hardware: ~500–700ns   ← fastest RAM, still honest
```

---

## 🔷 POLM on Polygon

Mine natively → Oracle registers blocks → Claim your ERC-20 POLM on Polygon.

| | |
|--|--|
| Contract | `0x79175931C54c9765E5846229a0eB118ef24fdE55` |
| Network | Polygon Mainnet (Chain ID 137) |
| Verified | Sourcify ✅  Blockscout ✅ |
| Claim fee | 0.5 POL |

[PolygonScan](https://polygonscan.com/token/0x79175931C54c9765E5846229a0eB118ef24fdE55) · [Claim POLM](https://polm.com.br/claim)

---

## 📊 Tokenomics

| Parameter | Value |
|-----------|-------|
| Symbol | POLM |
| Max supply | 210,000,000 |
| Block reward (Epoch 0) | 50 POLM (fixed) |
| Block time | 2 minutes |
| Halving interval | 100,000 blocks (~138 days) |
| Hash algorithm | SHA3-256 |
| Signatures | ECDSA secp256k1 |
| HD wallet | BIP-39 / BIP-44 |
| Pre-mine / ICO | **None** |
| Founder allocation | 10,500,000 POLM (5%) · locked 5 years on-chain |

### Epoch Schedule

| Epoch | Blocks | DAG | Min RAM | Reward |
|-------|--------|-----|---------|--------|
| **0 ← NOW** | 0–100k | 256 MB | 4 GB | 50 POLM |
| 1 | 100k–200k | 512 MB | 8 GB | 25 POLM |
| 2 | 200k–300k | 1 GB | 16 GB | 12.5 POLM |
| 3 | 300k–400k | 2 GB | 32 GB | 6.25 POLM |
| 4+ | ... | ... | ... | ... |

**Epoch 0 is the most accessible window** — any PC with 4 GB+ RAM mines today.

---

## 🛡 Security

| Attack | Defense |
|--------|---------|
| ASIC | 256 MB+ DAG — DRAM physics can't be miniaturized |
| GPU | GDDR latency ≥ DDR latency — no advantage |
| Cache exploit | Latency floor 400ns rejects cache L3 reads (~19ns) |
| Fake latency | Delta-T 30s enforced — can't submit faster than physics allows |
| Replay attack | Duplicate hash rejected in memory |
| Oracle fraud | Ed25519 cryptographic signature required |
| Rug pull | Founder locked 5 years — smart contract enforced |
| Sybil attack | 1 IP = max 10 active wallets |

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

Your node automatically connects to the network, downloads the blockchain and joins P2P.

---

## 🌐 REST API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Node status + summary |
| `/getwork` | GET | Mining job |
| `/submit` | POST | Submit mined block |
| `/chain` | GET | Block list |
| `/block/<h>` | GET | Block details |
| `/balance/<addr>` | GET | Address balance |
| `/miners` | GET | Leaderboard |
| `/connected_miners` | GET | Active miners |

---

## 📁 Repository

```
polm_miner_cli.py      ← Python CLI miner · auto-update · official
polm_miner_gui.py      ← GUI miner (Windows / Linux / macOS)
install.sh             ← Linux auto-installer
install_windows.ps1    ← Windows PowerShell installer
requirements.txt       ← Python dependencies
README.md              ← This file
WHITEPAPER.md          ← Technical whitepaper v3.0
roadmap.html           ← Project roadmap
legacy/                ← C miner source (archived)
```

---

## 🗺 Roadmap

- ✅ v1.0 — Algorithm designed and validated
- ✅ v2.0 — Pure latency consensus · any RAM mines
- ✅ Mainnet live — polm.com.br
- ✅ Polygon ERC-20 contract — verified + founder lock 5 years
- ✅ Oracle — auto-sustaining bridge
- ✅ Claim page — polm.com.br/claim
- ✅ GUI miner — Windows / Linux / macOS
- ✅ CLI miner — no dependencies · auto-update
- ✅ CPU auto-detection in explorer
- ✅ Full node published
- ✅ P2P network — DNS seeds + peer discovery
- ✅ Telegram Bot — @PolmNetworkBot (stats, rankings, block notifications)
- ✅ Security hardening — latency floor 400ns + Delta-T 30s
- ⬜ DEX listing — QuickSwap (Polygon)
- ⬜ Mining pool
- ⬜ CoinGecko / CoinMarketCap listing
- ⬜ CEX listing
- ⬜ PinkSale Fair Launch

---

## 👥 Community

| | |
|--|--|
| 🐦 Project | [@polmram](https://x.com/polmram) |
| 👤 Founder | [@aluisiofer](https://x.com/aluisiofer) |
| 📱 Telegram | [t.me/polm2026](https://t.me/polm2026) |
| 🤖 Bot | [@PolmNetworkBot](https://t.me/PolmNetworkBot) |
| 🗣 Bitcointalk | [topic=5579305](https://bitcointalk.org/index.php?topic=5579305) |
| ⚙️ GitHub | [proof-of-legacy](https://github.com/proof-of-legacy) |
| 📧 Contact | contact@polm.com.br |

---

> PoLM is experimental software. Not financial advice.  
> MIT License · © 2026 Aluísio Fernandes (Aluminium)  
> **Proof of Memory. Any RAM mines.**
