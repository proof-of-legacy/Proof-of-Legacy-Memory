# ⛏ PoLM — Proof of Legacy Memory

**The first RAM-latency-bound Proof-of-Work.**
Mine with any RAM. DDR2, DDR3, DDR4, DDR5 — every generation mines.
Score = 1/latency. Physics can't be faked.

[![Mainnet](https://img.shields.io/badge/network-mainnet-green)](https://polm.com.br)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Twitter](https://img.shields.io/badge/twitter-@polm2026-1DA1F2)](https://x.com/polm2026)

---

## 🟢 Mainnet Live

| | |
|--|--|
| 🌐 Website | https://polm.com.br |
| 🔍 Explorer | https://explorer.polm.com.br |
| 💰 Claim POLM | https://polm.com.br/claim |
| 🗺 Roadmap | https://polm.com.br/roadmap |
| ⚙️ Node API | https://polm.com.br/api/ |

---

## ⚡ Quick Start

### 🪟 Windows — PowerShell
```powershell
# Step 1: Install Python 3.11 from https://python.org
#         ✅ Check "Add Python to PATH" during installation

# Step 2: Download the miner
mkdir $env:USERPROFILE\polm
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/proof-of-legacy/Proof-of-Legacy-Memory/main/polm_miner_cli.py" -OutFile "$env:USERPROFILE\polm\miner.py"

# Step 3: Run
python $env:USERPROFILE\polm\miner.py
```

### 🐧 Linux / macOS — Terminal
```bash
# Download and run directly — no install needed
curl -O https://raw.githubusercontent.com/proof-of-legacy/Proof-of-Legacy-Memory/main/polm_miner_cli.py
python3 polm_miner_cli.py
```

> The miner will guide you through wallet creation and setup on first run.

---

## 🔷 POLM on Polygon

Mine natively → Oracle registers blocks → Claim your ERC-20 POLM on Polygon.
```
Contract:  0x79175931C54c9765E5846229a0eB118ef24fdE55
Network:   Polygon Mainnet (Chain ID 137)
Verified:  Sourcify ✅  Blockscout ✅
Claim fee: 0.5 MATIC
```

🔗 [PolygonScan](https://polygonscan.com/token/0x79175931C54c9765E5846229a0eB118ef24fdE55) · [Claim POLM](https://polm.com.br/claim) · DEX listing coming soon — QuickSwap

---

## 🧠 Algorithm
```
score = 1 / latency_ns
```

No boost multiplier. No penalty. Pure physics.

- **Slower RAM** → higher latency → higher score per step → valid block
- **Faster RAM** → lower latency → more nonces per second → valid block

### How it works

1. **Memory DAG** — Pseudorandom 256 MB+ buffer seeded from chain state. Every access is a real DRAM read — CPU cache completely bypassed.
2. **Sequential walk** — 100,000 steps per nonce, each depending on the previous. Impossible to parallelize.
3. **Physics enforces score** — The network measures real hardware latency. It cannot be faked.

### Any RAM Mines

| Generation | Avg Latency | Profile |
|-----------|------------|---------|
| DDR2 | ~3500–8000 ns | High latency → high score/step ✅ |
| DDR3 | ~1500–4000 ns | Balanced latency profile ✅ |
| DDR4 | ~900–1900 ns | More nonces per second ✅ |
| DDR5 | ~500–900 ns | Highest nonce throughput ✅ |

---

## 📊 Tokenomics

| Parameter | Value |
|-----------|-------|
| Symbol | **POLM** |
| Max supply | 210,000,000 |
| Block reward (Epoch 0) | 50 POLM |
| Block time | 2 minutes |
| Halving interval | 100,000 blocks (~138 days) |
| Hash algorithm | SHA3-256 |
| Signatures | ECDSA secp256k1 |
| HD wallet | BIP-39 / BIP-44 |
| Pre-mine / ICO | **None** |
| Founder allocation | 10,500,000 POLM (5%) · locked 5 years |

### Epoch Schedule

| Epoch | Blocks | DAG | Min RAM | Reward |
|-------|--------|-----|---------|--------|
| **0 ← NOW** | 0–100k | 256 MB | 4 GB | **50 POLM** |
| 1 | 100k–200k | 512 MB | 16 GB | 25 POLM |
| 2 | 200k–300k | 1 GB | 32 GB | 12.5 POLM |
| 3 | 300k–400k | 2 GB | 64 GB | 6.25 POLM |
| 4 | 400k–500k | 4 GB | 128 GB | 3.125 POLM |
| 5 | 500k–600k | 8 GB | 256 GB | 1.5625 POLM |
| 6 | 600k–700k | 16 GB | 512 GB | 0.781 POLM |
| 7 ⚡ | 700k–800k | 32 GB | 1 TB | 0.390 POLM |
| 8+ 🏭 | 800k+ | 64 GB+ | 2 TB+ | 0.195 POLM |

> **Epoch 0** is the most accessible window — any PC with 4 GB+ RAM mines today.

---

## 🛡 Security

| Attack | Defense |
|--------|---------|
| ASIC | 256 MB+ DAG — DRAM physics can't be miniaturized |
| GPU | GDDR latency ≥ DDR latency — no advantage |
| Cache exploit | Latency < 5ns → block rejected |
| Fake RAM | Score measures real latency — hardware auto-detected |
| Oracle fraud | ECDSA signature required on every block |
| Rug pull | Founder locked 5 years — smart contract enforced |

---

## 📁 Repository
```
polm.py               ← Full node + CLI miner
polm_miner_cli.py     ← Standalone CLI miner (no dependencies)
polm_miner_gui.py     ← GUI miner (Windows / Linux / macOS)
polm_explorer.py      ← Blockchain explorer
polm_bip39.py         ← BIP-39/BIP-32 HD wallet
polm_bridge_oracle.py ← Polygon bridge oracle (ECDSA)
polm_wallet.py        ← Web wallet UI
requirements.txt      ← flask cryptography mnemonic requests
```

---

## 🌐 REST API

| Endpoint | Method | Description |
|---------|--------|-------------|
| `/` | GET | Node status + summary |
| `/getwork` | GET | Mining job |
| `/submit` | POST | Submit mined block |
| `/register_evm` | POST | Register Polygon wallet |
| `/chain` | GET | Block list |
| `/block/<h>` | GET | Block details |
| `/balance/<addr>` | GET | Address balance |
| `/miners` | GET | Leaderboard with CPU info |

---

## 🗺 Roadmap

- [x] v1.0 — Algorithm designed and validated
- [x] v2.0 — Pure latency consensus · any RAM mines
- [x] Mainnet live — polm.com.br
- [x] Polygon ERC-20 contract — verified + founder lock 5 years
- [x] Oracle ECDSA — auto-sustaining bridge
- [x] Claim page — polm.com.br/claim
- [x] GUI miner — Windows / Linux / macOS
- [x] CLI miner — no dependencies, Windows & Linux
- [x] CPU auto-detection in explorer leaderboard
- [ ] DEX listing — QuickSwap (Polygon)
- [ ] CoinGecko / CoinMarketCap listing
- [ ] Mining pool
- [ ] CEX listing
- [ ] RAM mining board ecosystem (Epoch 7)

---

## 👥 Community

| | |
|--|--|
| 🐦 Project | [@polm2026](https://x.com/polm2026) |
| 👤 Founder | [@aluisiofer](https://x.com/aluisiofer) |
| ⚙️ GitHub | [proof-of-legacy](https://github.com/proof-of-legacy/Proof-of-Legacy-Memory) |
| 📧 Contact | contact@polm.com.br |

---

> PoLM is experimental software. Not financial advice.
> MIT License · © 2026 Aluísio Fernandes (Aluminium)
