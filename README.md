# PoLM — Proof of Legacy Memory

<div align="center">

**https://polm.com.br**

[![Version](https://img.shields.io/badge/version-1.3.1-22d3ee?style=flat-square)](https://github.com/proof-of-legacy/Proof-of-Legacy-Memory)
[![Network](https://img.shields.io/badge/network-mainnet-22c55e?style=flat-square)](http://node1.polm.com.br:6060)
[![License](https://img.shields.io/badge/license-MIT-3d5166?style=flat-square)](LICENSE)
[![Twitter](https://img.shields.io/badge/twitter-@polm2026-1d9bf0?style=flat-square)](https://x.com/polm2026)

*The first RAM-latency-bound Proof-of-Work.*  
*A 2006 Core 2 Duo with DDR2 mines 52% of all blocks — beating every modern machine.*

</div>

---

## What is PoLM?

Most Proof-of-Work algorithms reward whoever has the most powerful hardware. PoLM flips this: the bottleneck is **real DRAM latency** — a physical property that cannot be miniaturized, parallelized, or replicated in ASIC silicon.

- **DDR2 (2006)** gets **12× boost** — dominates in the early years
- **DDR5 (2023)** gets **0.5× penalty** — too fast, punished by design
- **16-thread i5** gets **0.25× penalty** — server CPUs don't help
- By **year 12**, you'll need 256GB RAM → new hardware market: **RAM mining motherboards**

## 🟢 Mainnet Live

```
Node:     http://node1.polm.com.br:6060
Explorer: http://explorer.polm.com.br:5050
Website:  https://polm.com.br
Genesis:  87df8a87c7befd2cde053569ed89c03f6502b33f4a910bb47284e66277a77fa5
```

## Proven on real hardware — 816 testnet blocks

| Rank | Hardware | RAM | Latency | Boost | Blocks | Share |
|------|----------|-----|---------|-------|--------|-------|
| 🥇 | Core 2 Duo 2006 | DDR2 | ~3800 ns | **12×** | 428 | **52.4%** |
| 🥈 | i5 7th gen 4t | DDR4 | ~1741 ns | 1× | 284 | 34.8% |
| 🥉 | AMD 2t | DDR3 | ~12988 ns | **10×** | 62 | 7.6% |
| 4 | i5 12th gen 16t | DDR4 | ~1060 ns | 1× (0.25 pen.) | 43 | 5.3% |

**A 2006 Core 2 Duo with DDR2 mined 52.4% of all blocks.**

---

## Quick Start

### Linux / macOS
```bash
git clone https://github.com/proof-of-legacy/Proof-of-Legacy-Memory.git
cd Proof-of-Legacy-Memory
bash scripts/install.sh

# Mine on mainnet
python3 polm.py miner http://node1.polm.com.br:6060 YOUR_ADDRESS DDR2
```

### Windows
```
1. Install Python 3.9+ from python.org (check "Add to PATH")
2. Double-click: scripts\install.bat
3. Double-click: start_all.bat
4. Browser opens → http://localhost:7070
```

---

## Algorithm

### Score formula
```
score = (1 / latency_ns) × boost × thread_penalty
```
Older hardware → higher latency → higher boost → more blocks.

### Evolutionary boost system (v1.3.1)

The protocol evolves every **2 years** (halving). RAM requirements grow, creating demand for specialized hardware:

| Year | Halving | DAG | Min RAM | DDR2 | DDR3 | DDR4 | DDR5 | DDR6 |
|------|---------|-----|---------|------|------|------|------|------|
| 0–2  | 1 | 256MB | 4GB | **12×** | **10×** | 1× | 0.5× | 0.3× |
| 2–4  | 2 | 512MB | 8GB | 10× | 8× | **4×** | 2× | 0.5× |
| 4–6  | 3 | 1GB | 16GB | 6× | 5× | **6×** | **4×** | 1× |
| 6–8  | 4 | 2GB | 32GB | 3× | 3× | **8×** | **6×** | 2× |
| 8–10 | 5 | 4GB | 64GB | 2× | 2× | 6× | **8×** | 4× |
| 10–12 | 6 | 8GB | 128GB | 1× | 1× | 4× | **10×** | 8× |
| **12–14** | **7** | **16GB** | **256GB** | 0.5× | 0.5× | 3× | 8× | **12×** ← RAM board! |
| 14+ | 8 | 32GB | 512GB | 0.2× | 0.2× | 2× | 6× | 10× |

> **Year 12**: requires 256GB RAM → forces creation of **dedicated RAM mining motherboards**, just like GPUs transformed SHA-256 mining.

### Thread saturation penalty (v1.3.1 — more aggressive)

| Threads | Penalty | Notes |
|---------|---------|-------|
| 1–2 | **1.00×** | Core2Duo, old laptops — full reward |
| 3–4 | 0.75× | Old quad-core |
| 5–8 | 0.50× | Mid-range |
| 9–16 | **0.25×** | Modern i5/i7 — 75% penalty |
| 17+ | 0.10× | Server CPU — 90% penalty |

---

## Economics

### Reward schedule (like Bitcoin)

| Period | Blocks | Reward | Year | Supply mined |
|--------|--------|--------|------|-------------|
| 1 | 0 – 2,099,999 | **50 POLM** | 0–2 | +105M |
| 2 | 2.1M – 4.2M | 25 POLM | 2–4 | +52.5M |
| 3 | 4.2M – 6.3M | 12.5 POLM | 4–6 | +26.2M |
| 4 | 6.3M – 8.4M | 6.25 POLM | 6–8 | +13.1M |
| 5+ | continuing... | halving... | ... | → 210M total |

**Max supply: 210,000,000 POLM** (~210 million, over 30+ years)

### Founder allocation
| Parameter | Value |
|-----------|-------|
| Address | `POLMD872771E5F0017C5B5C08D353B5E7B4B` |
| Lock | 5,256,000 blocks (~5 years) |
| Founder | Aluísio Fernandes (Aluminium) — [@aluisiofer](https://x.com/aluisiofer) |

---

## Protocol Parameters

| Parameter | Testnet | Mainnet |
|-----------|---------|---------|
| Symbol | POLM | POLM |
| Max Supply | — | 210,000,000 |
| Block Time | 30s | 30s |
| Initial Reward | 5.0 POLM | **50.0 POLM** |
| Halving Interval | 4,200,000 | **2,100,000 (~2yr)** |
| DAG Size | 4 MB | 256 MB + 64 MB/epoch |
| Walk Steps | 500 | 100,000 |
| Difficulty Retarget | 144 blocks (±25%) | 144 blocks (±25%) |
| Hash Algorithm | SHA3-256 | SHA3-256 |
| Initial Difficulty | 4 | **3** |

---

## REST API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Node status + chain summary |
| `/getwork` | GET | Mining job + pending transactions |
| `/submit` | POST | Submit mined block |
| `/tx/send` | POST | Broadcast transaction |
| `/chain` | GET | Block list (`?limit=N&offset=N`) |
| `/block/<h>` | GET | Block + transactions |
| `/balance/<addr>` | GET | Address balance |
| `/miners` | GET | Mining leaderboard |
| `/peers` | GET | Connected peers |

---

## Files

```
polm.py          ← Full node + miner (Windows / Linux / macOS)
polm_wallet.py   ← Web wallet UI + CLI
polm_explorer.py ← Blockchain explorer v2.1.0
polm_bip39.py    ← BIP-39/BIP-32 HD wallet
requirements.txt ← flask cryptography mnemonic requests
scripts/
├── install.bat  ← Windows one-click installer
└── install.sh   ← Linux / macOS installer
```

---

## Security

| Attack | Defense |
|--------|---------|
| ASIC | 256MB+ DAG + latency-hard walk — DRAM physics can't be miniaturized |
| GPU | GDDR latency > DDR latency — no advantage |
| Cache exploit | Latency < 5ns → block rejected |
| Fake RAM | Dynamic boost measures real latency, not declared type |
| Multi-thread | Heavy thread penalty — 16 threads = 0.25× multiplier |

---

## Roadmap

- [x] v1.0 — PoLM algorithm validated on real hardware
- [x] v1.2 — Mainnet ready · polm.com.br · 816 testnet blocks
- [x] **v1.3.1 — Mainnet live · 50 POLM/block · evolutionary RAM protocol** ← current
- [ ] v1.4 — Mining UI (one-click miner for non-technical users)
- [ ] v2.0 — Rust/Go production node
- [ ] Trust Wallet / MetaMask integration
- [ ] CoinMarketCap / CoinGecko listing
- [ ] RAM mining motherboard ecosystem (year 12 target)

---

## Community

| Channel | Link |
|---------|------|
| Website | https://polm.com.br |
| Explorer | http://explorer.polm.com.br:5050 |
| Project Twitter | https://x.com/polm2026 |
| Founder Twitter | https://x.com/aluisiofer |
| GitHub | https://github.com/proof-of-legacy/Proof-of-Legacy-Memory |

---

*PoLM is experimental software. Not financial advice.*  
*MIT License · © 2026 Aluísio Fernandes (Aluminium)*
