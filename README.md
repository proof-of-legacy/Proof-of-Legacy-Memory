# PoLM — Proof of Legacy Memory
**https://polm.com.br**

[![Version](https://img.shields.io/badge/version-2.0.0-cyan)](https://polm.com.br)
[![Network](https://img.shields.io/badge/network-mainnet-green)](https://explorer.polm.com.br)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Twitter](https://img.shields.io/badge/twitter-@polm2026-1DA1F2)](https://x.com/polm2026)

> **Mine with any RAM. Latency is truth.**

The first RAM-latency-bound Proof-of-Work. DDR2, DDR3, DDR4, DDR5 — every generation mines. Score = 1/latency. Physics can't be faked.

---

## 🟢 Mainnet Live

```
Node:       https://polm.com.br/api/
Explorer:   https://explorer.polm.com.br
Claim POLM: https://polm.com.br/claim
Roadmap:    https://polm.com.br/roadmap
Version:    2.0.0
```

---

## 🔷 POLM Token on Polygon

ERC-20 token on Polygon Mainnet. Mine natively → Oracle registers blocks → Claim your POLM.

```
Contract:    0x79175931C54c9765E5846229a0eB118ef24fdE55
Network:     Polygon Mainnet (Chain ID 137)
Verified:    Sourcify ✅ + Blockscout ✅
Claim fee:   0.5 MATIC (auto-sustaining)
```

🔗 [PolygonScan](https://polygonscan.com/token/0x79175931C54c9765E5846229a0eB118ef24fdE55) | [Claim POLM](https://polm.com.br/claim)

> **📈 DEX listing coming soon — QuickSwap (Polygon)**

---

## What is PoLM?

Most Proof-of-Work algorithms reward whoever has the most powerful hardware. PoLM is different: the bottleneck is real DRAM latency — a physical property that cannot be miniaturized, parallelized, or replicated in ASIC silicon.

- **No artificial boost** — no multipliers by RAM type
- **No penalties** — no thread saturation penalty
- **Score = 1 / latency_ns** — pure physics, nothing else
- **Any RAM mines** — DDR2 to DDR5, all generations compete honestly

---

## Quick Start

### 🪟 Windows EXE — easiest, no Python needed!

1. Download **[PoLM-Miner.exe](https://github.com/proof-of-legacy/Proof-of-Legacy-Memory/releases/latest)**
2. Double-click to open
3. Enter your POLM wallet address
4. Enter your Polygon/Trust wallet
5. Click **START MINING** ⛏

> Verify SHA256: `Get-FileHash PoLM-Miner.exe -Algorithm SHA256` and compare with `PoLM-Miner.exe.sha256`

### 🪟 Windows (PowerShell)

1. Install **Python 3.9+** from [python.org](https://www.python.org/downloads/) *(check "Add to PATH")*
2. Download this repository as ZIP and extract
3. Double-click **`scripts/install_windows.bat`**
4. Double-click **`start_miner.bat`**
5. Enter your Polygon/Trust wallet address
6. Click **START MINING** ⛏

### 🐧 Linux / macOS (GUI)

```bash
git clone https://github.com/proof-of-legacy/Proof-of-Legacy-Memory.git
cd Proof-of-Legacy-Memory
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 polm_miner_gui.py
```

### 🐧 Linux / macOS (Command line)

```bash
git clone https://github.com/proof-of-legacy/Proof-of-Legacy-Memory.git
cd Proof-of-Legacy-Memory
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Create wallet
python3 polm_bip39.py new "My Wallet"

# Start mining
python3 polm.py miner https://polm.com.br/api/ YOUR_POLM_ADDRESS
```

---

## Algorithm

```
score = 1 / latency_ns
```

That's it. No boost multiplier. No penalty. Pure physics.

- **Slower RAM** → higher latency → higher score per step → valid block
- **Faster RAM** → lower latency → more nonces per second → valid block

### How it works

1. **Build the Memory DAG** — Each epoch seeds a pseudorandom buffer from chain state (256 MB in Epoch 0, doubling each epoch). Every access is a real DRAM read — CPU cache is completely bypassed.

2. **Sequential memory walk** — 100,000 steps per nonce, each depending on the previous. Impossible to parallelize. The only bottleneck is physical DRAM latency.

3. **Physics enforces the score** — Score = 1 / latency_ns. The network measures real hardware latency. It cannot be faked.

---

## Any RAM Mines

| Generation | Avg Latency | Profile | Status |
|-----------|------------|---------|--------|
| DDR2 | ~3500–8000 ns | High latency → high score/step | ✅ Mines now |
| DDR3 | ~1500–4000 ns | Balanced latency profile | ✅ Mines now |
| DDR4 | ~900–1900 ns | More nonces per second | ✅ Mines now |
| DDR5 | ~500–900 ns | Highest nonce throughput | ✅ Mines now |

No favorites. No losers. Every generation contributes honestly to the network.

---

## Epoch Schedule

| Epoch | Blocks | ~Days | DAG | Min RAM | Reward | Who mines? |
|-------|--------|-------|-----|---------|--------|-----------|
| **0 ← NOW** | 0–100k | ~138d | 256 MB | 4 GB | **50 POLM** | Any PC with 4 GB+ RAM |
| 1 | 100k–200k | ~138d | 512 MB | 16 GB | 25 POLM | Most modern desktops |
| 2 | 200k–300k | ~138d | 1 GB | 32 GB | 12.5 POLM | High-end workstations |
| 3 | 300k–400k | ~138d | 2 GB | 64 GB | 6.25 POLM | Server-class machines |
| 4 | 400k–500k | ~138d | 4 GB | 128 GB | 3.125 POLM | Dedicated RAM rigs |
| 5 | 500k–600k | ~138d | 8 GB | 256 GB | 1.5625 POLM | Enterprise RAM servers |
| 6 | 600k–700k | ~138d | 16 GB | 512 GB | 0.781 POLM | RAM mining boards |
| 7 ⚡ | 700k–800k | ~138d | 32 GB | 1 TB | 0.390 POLM | Industrial RAM arrays! |
| 8+ 🏭 | 800k+ | — | 64 GB+ | 2 TB+ | 0.195 POLM | New hardware industry |

> **Epoch 0 is the most accessible window** — any machine with 4 GB+ RAM can mine today.

---

## Economics

### Token parameters

| Parameter | Value |
|-----------|-------|
| Symbol | POLM |
| Max supply | 210,000,000 |
| Block reward (Epoch 0) | 50 POLM |
| Block time | 2 minutes (120s) |
| Halving interval | 100,000 blocks per epoch (~138 days) |
| Difficulty retarget | every 144 blocks (±25%) |
| Hash algorithm | SHA3-256 |
| Signatures | ECDSA secp256k1 |
| HD wallet | BIP-39 / BIP-44 |
| Max threads | 4 per miner |
| Pre-mine / ICO | None |
| Founder allocation | 10,500,000 POLM (5%) · locked 5 years |

### Polygon ERC-20 Bridge

| Parameter | Value |
|-----------|-------|
| Contract | `0x79175931C54c9765E5846229a0eB118ef24fdE55` |
| Network | Polygon Mainnet (Chain ID 137) |
| Claim fee | 0.5 MATIC |
| Fee split | 80% dev · 20% oracle |
| Oracle | ECDSA signed — fraud impossible |
| Verified | Sourcify ✅ Blockscout ✅ |
| DEX | Coming soon — QuickSwap |

### Founder allocation

| Parameter | Value |
|-----------|-------|
| Native address | POLMD872771E5F0017C5B5C08D353B5E7B4B |
| Polygon address | 0xFFC18CB440B0CDCa072caa0A3DFcA6c049d9262b |
| Polygon allocation | **10,500,000 POLM (5%)** |
| Lock | **5,256,000 blocks (~5 years) — smart contract enforced** |
| Founder | Aluísio Fernandes (Aluminium) — @aluisiofer |

---

## Security

| Attack | Defense |
|--------|---------|
| ASIC | 256 MB+ DAG + latency-hard walk — DRAM physics can't be miniaturized |
| GPU | GDDR latency ≥ DDR latency — no advantage |
| Cache exploit | Latency < 5ns → block rejected |
| Fake RAM | Score measures real latency, not declared type — hardware auto-detected |
| Manual RAM override | GUI detects RAM from hardware — cannot be overridden by user |
| Oracle fraud | ECDSA signature required on every block registration |
| Rug pull | Founder locked 5 years on-chain — smart contract enforced |

---

## Files

```
polm.py               ← Full node + miner (Linux / macOS CLI)
polm_miner_gui.py     ← GUI miner (Windows / Linux / macOS)
polm_explorer.py      ← Blockchain explorer v2.2.0
polm_bip39.py         ← BIP-39/BIP-32 HD wallet
polm_wallet.py        ← Web wallet UI + CLI
polm_bridge_oracle.py ← Polygon bridge oracle (ECDSA)
requirements.txt      ← flask cryptography mnemonic requests
scripts/
├── install_windows.bat ← Windows one-click installer
└── install.sh          ← Linux / macOS installer
```

---

## REST API

| Endpoint | Method | Description |
|---------|--------|-------------|
| `/` | GET | Node status + chain summary |
| `/getwork` | GET | Mining job + pending transactions |
| `/submit` | POST | Submit mined block |
| `/register_evm` | POST | Register Polygon wallet address |
| `/tx/send` | POST | Broadcast transaction |
| `/chain` | GET | Block list (?limit=N&offset=N) |
| `/block/<h>` | GET | Block + transactions |
| `/balance/<addr>` | GET | Address balance |
| `/miners` | GET | Mining leaderboard with CPU info |
| `/peers` | GET | Connected peers |

---

## Roadmap

- [x] v1.0 — PoLM algorithm designed and validated
- [x] v1.2 — Mainnet ready · polm.com.br
- [x] v2.0 — Pure latency consensus · any RAM mines · epoch halving
- [x] Polygon ERC-20 contract — verified + founder lock 5 years
- [x] Oracle ECDSA — auto-sustaining bridge
- [x] Claim page — polm.com.br/claim
- [x] **GUI miner — Windows / Linux / macOS (polm_miner_gui.py)**
- [x] `/register_evm` API — automatic Polygon wallet registration
- [ ] DEX listing — QuickSwap (Polygon) — **coming soon**
- [ ] CoinMarketCap / CoinGecko listing
- [ ] Mining pool
- [ ] CEX listing
- [ ] RAM mining board ecosystem (Epoch 7 — 1 TB arrays)

---

## Community

| Channel | Link |
|---------|------|
| Website | https://polm.com.br |
| Explorer | https://explorer.polm.com.br |
| Claim POLM | https://polm.com.br/claim |
| Roadmap | https://polm.com.br/roadmap |
| Project Twitter | https://x.com/polm2026 |
| Founder Twitter | https://x.com/aluisiofer |
| Download EXE | https://github.com/proof-of-legacy/Proof-of-Legacy-Memory/releases/latest |
| GitHub | https://github.com/proof-of-legacy/Proof-of-Legacy-Memory |

---

> *PoLM is experimental software. Not financial advice.*
> MIT License · © 2026 Aluísio Fernandes (Aluminium)
