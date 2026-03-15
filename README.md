# PoLM-X v2 — Proof of Legacy Memory (Extended)

> **Memory-Hard + Latency-Hard** consensus — giving old hardware a second life.

[![Version](https://img.shields.io/badge/version-2.0.0-00e5ff?style=flat-square&labelColor=0d1520)](.)
[![Status](https://img.shields.io/badge/status-testnet-ffb300?style=flat-square&labelColor=0d1520)](.)
[![Python](https://img.shields.io/badge/python-3.9%2B-00ff88?style=flat-square&labelColor=0d1520)](.)

---

## What is PoLM-X?

PoLM-X is a Proof-of-Work algorithm where the bottleneck is **real DRAM latency** — something that cannot be easily miniaturized or parallelized. Unlike SHA-256 (CPU/ASIC) or Ethash (GPU VRAM), PoLM-X makes a Core 2 Duo with DDR2 genuinely competitive against a modern Ryzen with DDR5.

## Why it works

| Algorithm | Bottleneck | ASIC resistant? |
|-----------|-----------|-----------------|
| SHA-256   | Compute   | ✗ |
| Ethash    | VRAM BW   | Partial |
| RandomX   | CPU Cache | Partial |
| **PoLM-X** | **RAM Latency + Size** | **✓** |

## Legacy Boost Multipliers

| RAM | Multiplier |
|-----|-----------|
| DDR2 | **2.20×** |
| DDR3 | **1.60×** |
| DDR4 | 1.00× |
| DDR5 | 0.85× |

## Quick Start

```bash
# Clone
git clone https://github.com/proof-of-legacy/Proof-of-Legacy-Memory.git
cd Proof-of-Legacy-Memory

# Install dependencies
pip install -r requirements.txt

# Run a node (testnet)
python3 polm_x_node.py

# Run the explorer
python3 polm_x_explorer.py
# Open http://localhost:5050

# Create a wallet
python3 polm_x_wallet.py

# Mine (via API)
curl -X POST http://localhost:6060/mine/start \
  -H "Content-Type: application/json" \
  -d '{"miner_id":"YourAddress","ram_type":"DDR3"}'
```

## REST API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Node status |
| `/chain` | GET | Latest blocks |
| `/block/<height>` | GET | Block by height |
| `/balance/<address>` | GET | Address balance |
| `/tx/submit` | POST | Submit transaction |
| `/mine/start` | POST | Start mining |
| `/mine/stop` | POST | Stop mining |
| `/validate` | GET | Full chain validation |
| `/network/info` | GET | Network parameters |

## Protocol Parameters

| Parameter | Value |
|-----------|-------|
| Symbol | POLM |
| Max Supply | 32,000,000 |
| Block Time | 30 seconds |
| Initial Reward | 5.0 POLM |
| Halving | ~4 years |
| Min RAM (epoch 0) | 4 GB |
| DAG Size (epoch 0) | 2 GB |
| Epoch Length | 100,000 blocks |

## Files

| File | Description |
|------|-------------|
| `polm_x_core.py` | Core engine: DAG, memory walk, blockchain, miner |
| `polm_x_node.py` | Full node with REST API and P2P |
| `polm_x_wallet.py` | ECDSA wallet |
| `polm_x_explorer.py` | Web explorer UI |
| `WHITEPAPER.md` | Full protocol specification |

## Status

🟡 **Experimental Testnet** — not ready for mainnet

## Supply

Total supply: **32,000,000 POLM** — a tribute to the 32-bit computing era.

---

*PoLM-X is experimental software. Not financial advice.*
