# PoLM — Proof of Legacy Memory

> **The first RAM-latency-bound Proof-of-Work consensus algorithm.**  
> Giving computational relevance back to legacy hardware.

[![Version](https://img.shields.io/badge/version-3.0.0-00e5ff?style=flat-square&labelColor=0d1520)](.)
[![Status](https://img.shields.io/badge/status-testnet-ffb300?style=flat-square&labelColor=0d1520)](.)
[![Python](https://img.shields.io/badge/python-3.9%2B-00ff88?style=flat-square&labelColor=0d1520)](.)
[![License](https://img.shields.io/badge/license-MIT-white?style=flat-square&labelColor=0d1520)](LICENSE)

---

## What is PoLM?

Most cryptocurrencies reward whoever has the most powerful hardware. PoLM flips this: the bottleneck is **real DRAM latency** — a physical property that cannot be miniaturized, parallelized, or easily optimized with ASICs.

A **Core 2 Duo from 2006 with DDR2** is genuinely competitive against a modern Ryzen with DDR5.

### Proven in the real world

On March 15, 2026, a 3-node testnet validated the algorithm with real hardware:

| Miner | CPU | RAM | Latency | Boost | Blocks |
|-------|-----|-----|---------|-------|--------|
| POLM_Aluisio | i5 12th gen | DDR4 | ~1060 ns | 1.00× | 34 |
| POLM6837… | i5 7th gen | DDR4 | ~1610 ns | 1.00× | 13 |
| **POLMBE9E…** | **Core 2 Duo** | **DDR2** | **~6746 ns** | **2.20×** | **1** ✅ |

Block #47 was mined by a Core 2 Duo — proving the concept works on real legacy hardware.

---

## How it works

```
getwork()
    ↓
Build Memory DAG (seeded from epoch + prev_hash)
    ↓
Random Memory Walk (N steps)
    ├─ Each step: pos = H(prev_hash) % DAG_size
    ├─ Read 32 bytes from DAG[pos]
    ├─ H_new = sha3_256(H_prev ∥ DAG[pos])
    └─ Measure access latency (nanoseconds)
    ↓
Latency Proof embedded in block header
    ↓
submit() → Central node validates + adds to chain
```

### Legacy Boost

| RAM Type | Multiplier | Typical Latency |
|----------|-----------|----------------|
| DDR2 | **2.20×** | ~6000–8000 ns |
| DDR3 | **1.60×** | ~1500–3000 ns |
| DDR4 | 1.00× | ~900–1600 ns |
| DDR5 | 0.85× | ~500–900 ns |

### Saturation Penalty

| Threads | Penalty |
|---------|---------|
| 1–4 | 1.00× |
| 5–8 | 0.90× |
| 9–16 | 0.80× |
| 17+ | 0.70× |

---

## Architecture

```
┌─────────────────────────────┐
│   Central Node (any PC)     │  ← stores blockchain, validates blocks
│   polm.py node              │  ← REST API: /getwork /submit /chain
└──────────────┬──────────────┘
               │ HTTP
    ┌──────────┼──────────┐
    ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐
│ Miner  │ │ Miner  │ │ Miner  │  ← any PC on the network
│ DDR2   │ │ DDR4   │ │ DDR4   │  ← polm.py miner <node_ip> <id> <ram>
└────────┘ └────────┘ └────────┘
```

Single file. No complex sync. Miners just call `/getwork`, mine, and `/submit`.

---

## Quick Start

### Requirements

```bash
pip install flask
```

### 1. Start the central node

```bash
python3 polm.py node
# Node running at http://0.0.0.0:6060
```

### 2. Start miners (any PC on the network)

```bash
# Same machine
python3 polm.py miner 127.0.0.1 MyMinerName DDR4

# Remote machine
python3 polm.py miner 192.168.0.103 MyMinerName DDR3

# Syntax
python3 polm.py miner <NODE_IP> <MINER_ID> <RAM_TYPE>
# RAM_TYPE: DDR2 | DDR3 | DDR4 | DDR5
```

### 3. Check the network

```bash
# Node status
curl http://localhost:6060/

# Latest blocks
curl http://localhost:6060/chain?limit=10

# Miner leaderboard
curl http://localhost:6060/miners

# Current work
curl http://localhost:6060/getwork
```

---

## REST API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Node status and chain summary |
| `/getwork` | GET | Current mining job (height, prev_hash, difficulty) |
| `/submit` | POST | Submit a mined block |
| `/chain` | GET | List blocks (`?limit=N&offset=N`) |
| `/block/<height>` | GET | Get block by height |
| `/balance/<address>` | GET | Address balance |
| `/miners` | GET | Leaderboard with stats per miner |

---

## Protocol Parameters

| Parameter | Value |
|-----------|-------|
| Symbol | POLM |
| Max Supply | 32,000,000 |
| Block Time Target | 30 seconds |
| Initial Reward | 5.0 POLM |
| Halving | Every ~4 years |
| Difficulty Retarget | Every 144 blocks (±25% max) |
| Epoch Length | 100,000 blocks |
| Hash Algorithm | SHA3-256 |

---

## Protocol Security

| Attack | Defense |
|--------|---------|
| ASIC | Large DAG + latency-hard — can't compress DRAM physics |
| GPU | GDDR has higher latency than DDR, neutralizing bandwidth advantage |
| Cache exploit | Latency < 5ns → block rejected |
| Fake RAM | Latency measured per-access, embedded in block header |
| Replay | Each block commits to prev_hash + timestamp + nonce |

---

## Economics

Supply schedule (32,000,000 POLM total — tribute to the 32-bit era):

| Period | Reward | Approx Supply |
|--------|--------|--------------|
| Year 1–4 | 5.0 POLM | ~21M |
| Year 5–8 | 2.5 POLM | ~27M |
| Year 9–12 | 1.25 POLM | ~30M |
| Year 13+ | 0.625 POLM… | →32M |

---

## Files

```
polm.py          ← entire protocol in one file
README.md        ← this file
WHITEPAPER.md    ← full technical specification
LICENSE          ← MIT
```

---

## Roadmap

- [x] v1.0 — Basic PoW with RAM latency measurement
- [x] v2.0 — Memory DAG + latency proof + legacy boost
- [x] v3.0 — Pool architecture (central node + remote miners) ✅ **current**
- [ ] v3.1 — Web explorer
- [ ] v3.2 — Wallet with ECDSA signatures
- [ ] v3.3 — P2P gossip (multiple full nodes)
- [ ] v4.0 — Mainnet genesis

---

## Status

🟡 **Experimental Testnet** — algorithm validated, not production ready.

---

*PoLM is experimental software. Not financial advice.*
