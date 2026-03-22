# PoLM — Proof of Legacy Memory

**https://polm.com.br**

![Version](https://img.shields.io/badge/version-2.0.0-cyan)
![Network](https://img.shields.io/badge/network-mainnet-green)
![License](https://img.shields.io/badge/license-MIT-blue)
![Twitter](https://img.shields.io/badge/twitter-@polm2026-1da1f2)

> **Mine with any RAM. Latency is truth.**

The first RAM-latency-bound Proof-of-Work. DDR2, DDR3, DDR4, DDR5 — every generation mines. Score = 1/latency. Physics can't be faked.

---

## What is PoLM?

Most Proof-of-Work algorithms reward whoever has the most powerful hardware. PoLM is different: the bottleneck is real **DRAM latency** — a physical property that cannot be miniaturized, parallelized, or replicated in ASIC silicon.

- **No artificial boost** — no multipliers by RAM type
- **No penalties** — no thread saturation penalty
- **Score = 1 / latency_ns** — pure physics, nothing else
- **Any RAM mines** — DDR2 to DDR5, all generations compete honestly
- Slower RAM scores higher per nonce; faster RAM compensates with more nonces per second
- By Epoch 7, mining requires **1 TB RAM** → a new hardware industry emerges

---

## 🟢 Mainnet Live

```
Node:     https://polm.com.br/api/
Explorer: https://explorer.polm.com.br
Website:  https://polm.com.br
Version:  2.0.0
```

---

## Quick Start

### Linux / macOS

```bash
git clone https://github.com/proof-of-legacy/Proof-of-Legacy-Memory.git
cd Proof-of-Legacy-Memory
bash scripts/install.sh

# Create wallet
python3 polm_bip39.py new "My Wallet"

# Start mining — no RAM type argument needed
python3 polm.py miner https://polm.com.br/api/ YOUR_ADDRESS
```

### Windows

```
1. Install Python 3.9+ from python.org (check "Add to PATH")
2. Double-click: scripts\install.bat
3. Double-click: start_miner.bat
```

---

## Algorithm

### Score formula

```
score = 1 / latency_ns
```

That's it. No boost multiplier. No penalty. **Pure physics.**

- Slower RAM → higher latency → higher score per step → valid block
- Faster RAM → lower latency → more nonces per second → valid block
- Every RAM generation has its natural place in the network

### How it works

1. **Build the Memory DAG** — Each epoch seeds a pseudorandom buffer from chain state (256 MB in Epoch 0, doubling each epoch). Every access is a real DRAM read — CPU cache is completely bypassed.

2. **Sequential memory walk** — 100,000 steps per nonce, each depending on the previous. Impossible to parallelize. The only bottleneck is physical DRAM latency.

3. **Physics enforces the score** — Score = 1 / latency_ns. The network measures real hardware latency. It cannot be faked.

---

## Any RAM Mines

| Generation | Avg Latency | Profile | Status |
|-----------|-------------|---------|--------|
| DDR2 | ~3500–8000 ns | High latency → high score/step | ✅ Mines now |
| DDR3 | ~1500–4000 ns | Balanced latency profile | ✅ Mines now |
| DDR4 | ~900–1900 ns | More nonces per second | ✅ Mines now |
| DDR5 | ~500–900 ns | Highest nonce throughput | ✅ Mines now |

No favorites. No losers. Every generation contributes honestly to the network.

---

## Epoch Schedule

Every 100,000 blocks (~138 days), the DAG doubles and the block reward halves. More RAM required each epoch — driving a new hardware upgrade cycle.

| Epoch | Blocks | ~Days | DAG | Min RAM | Reward | Who mines? |
|-------|--------|-------|-----|---------|--------|-----------|
| 0 ← NOW | 0–100k | ~138d | 256 MB | **4 GB** | **50 POLM** | Any PC with 4 GB+ RAM |
| 1 | 100k–200k | ~138d | 512 MB | 16 GB | 25 POLM | Most modern desktops |
| 2 | 200k–300k | ~138d | 1 GB | 32 GB | 12.5 POLM | High-end workstations |
| 3 | 300k–400k | ~138d | 2 GB | 64 GB | 6.25 POLM | Server-class machines |
| 4 | 400k–500k | ~138d | 4 GB | 128 GB | 3.125 POLM | Dedicated RAM rigs |
| 5 | 500k–600k | ~138d | 8 GB | 256 GB | 1.5625 POLM | Enterprise RAM servers |
| 6 | 600k–700k | ~138d | 16 GB | 512 GB | 0.781 POLM | RAM mining boards |
| 7 ⚡ | 700k–800k | ~138d | 32 GB | **1 TB** | 0.390 POLM | Industrial RAM arrays! |
| 8+ 🏭 | 800k+ | — | 64 GB+ | **2 TB+** | 0.195 POLM | New hardware industry |

> Epoch 0 is the most accessible window — **any machine with 4 GB+ RAM can mine today**.

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
| Founder allocation | 5% · locked 5 years |

### Emission schedule

| Epoch | Reward | POLM minted |
|-------|--------|-------------|
| 0 | 50 POLM | +~720M blocks × 50 |
| 1 | 25 POLM | halving |
| 2 | 12.5 POLM | halving |
| 3 | 6.25 POLM | halving |
| 4+ | decreasing | → 210M total |

Full supply takes **30+ years** to mine completely.

### Founder allocation

| Parameter | Value |
|-----------|-------|
| Address | POLMD872771E5F0017C5B5C08D353B5E7B4B |
| Lock | 5,256,000 blocks (~5 years) |
| Founder | Aluísio Fernandes (Aluminium) — @aluisiofer |

---

## Protocol Parameters

| Parameter | Value |
|-----------|-------|
| Symbol | POLM |
| Network | mainnet |
| Version | 2.0.0 |
| Max Supply | 210,000,000 |
| Block Time | 120 seconds (2 min) |
| Initial Reward | 50.0 POLM |
| Halving Interval | 100,000 blocks (~138 days) |
| DAG Size (Epoch 0) | 256 MB |
| Walk Steps | 100,000 per nonce |
| Difficulty Retarget | 144 blocks (±25%) |
| Hash Algorithm | SHA3-256 |
| Score Formula | 1 / latency_ns |

---

## REST API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Node status + chain summary |
| `/getwork` | GET | Mining job + pending transactions |
| `/submit` | POST | Submit mined block |
| `/tx/send` | POST | Broadcast transaction |
| `/chain` | GET | Block list (?limit=N&offset=N) |
| `/block/<h>` | GET | Block + transactions |
| `/balance/<addr>` | GET | Address balance |
| `/miners` | GET | Mining leaderboard |
| `/peers` | GET | Connected peers |

---

## Security

| Attack | Defense |
|--------|---------|
| ASIC | 256 MB+ DAG + latency-hard walk — DRAM physics can't be miniaturized |
| GPU | GDDR latency ≥ DDR latency — no advantage |
| Cache exploit | Latency < 5ns → block rejected |
| Fake RAM | Score measures real latency, not declared type |
| Virtualization | VM DRAM latency is real and measurable — cannot be spoofed |

---

## Files

```
polm.py          ← Full node + miner (Windows / Linux / macOS)
polm_explorer.py ← Blockchain explorer v2.2.0
polm_bip39.py    ← BIP-39/BIP-32 HD wallet
polm_wallet.py   ← Web wallet UI + CLI
requirements.txt ← flask cryptography mnemonic requests
scripts/
├── install.bat  ← Windows one-click installer
└── install.sh   ← Linux / macOS installer
```

---

## Roadmap

- [x] v1.0 — PoLM algorithm designed and validated
- [x] v1.2 — Mainnet ready · polm.com.br
- [x] v2.0 — Pure latency consensus · any RAM mines · epoch halving ← **current**
- [ ] v2.1 — Mining UI (one-click miner for non-technical users)
- [ ] Bridge — Polygon DEX integration (~$0.001/tx)
- [ ] Trust Wallet / MetaMask integration
- [ ] CoinMarketCap / CoinGecko listing
- [ ] RAM mining board ecosystem (Epoch 7 target — 1 TB arrays)

---

## Community

| Channel | Link |
|---------|------|
| Website | https://polm.com.br |
| Explorer | https://explorer.polm.com.br |
| Project Twitter | https://x.com/polm2026 |
| Founder Twitter | https://x.com/aluisiofer |
| GitHub | https://github.com/proof-of-legacy/Proof-of-Legacy-Memory |
| Contact | contact@polm.com.br |

---

*PoLM is experimental software. Not financial advice.*  
*MIT License · © 2026 Aluísio Fernandes (Aluminium)*
