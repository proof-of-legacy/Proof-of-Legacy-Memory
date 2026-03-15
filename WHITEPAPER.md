# PoLM-X v2 — Proof of Legacy Memory (Extended)
## Whitepaper — Memory-Hard + Latency-Hard Consensus

---

> *"Every old computer deserves a second life."*

---

## Abstract

**PoLM-X** is a Proof-of-Work consensus algorithm that simultaneously enforces two independent hardware constraints: **Memory-Hard** (large RAM allocation) and **Latency-Hard** (real memory access latency). By combining both properties, PoLM-X creates a mining environment where legacy hardware (DDR2/DDR3 systems) remains economically competitive, while ASIC development becomes prohibitively difficult.

---

## 1. Motivation

Most Proof-of-Work algorithms optimize for one dimension:

| Algorithm | Bottleneck | Winner |
|-----------|-----------|--------|
| SHA-256   | Compute   | ASIC   |
| Ethash    | VRAM bandwidth | GPU |
| RandomX   | Cache + CPU | CPU  |
| Chia      | Storage   | HDD/SSD farm |
| **PoLM-X** | **RAM Size + RAM Latency** | **Legacy CPU** |

The consequence is inevitable centralization: whoever builds the best ASIC or GPU farm dominates. PoLM-X breaks this by making the bottleneck something that **cannot easily be miniaturized**: the physical latency of DRAM cells.

---

## 2. Protocol Overview

### 2.1 Architecture

```
Seed
 ↓
Memory DAG generation (seeded per epoch + prev_hash)
 ↓
Random Memory Walk (100,000 steps)
 ↓
Latency Measurement (per-access ns timing)
 ↓
Hash Chain (sha3-256, each step depends on previous)
 ↓
Latency Proof + Memory Proof embedded in header
 ↓
Block validation (PoW prefix + proof checks)
```

### 2.2 Key Components

| Component | Description |
|-----------|-------------|
| Memory DAG | Large pseudorandom buffer seeded from epoch + chain tip |
| Random Memory Walk | Unpredictable access pattern; each address derived from previous hash |
| Hash Chain | sha3-256 chain: `H(i) = sha3(H(i-1) ∥ DAG[pos])` |
| Latency Proof | Average ns per memory access, measured and embedded in block |
| Legacy Boost | Per-generation RAM multiplier rewarding older hardware |
| Saturation Penalty | Reduces score for high thread counts |

---

## 3. Memory DAG

The DAG is a large byte buffer, deterministically generated from:

```
dag_seed = sha3_256( "polmx:" ∥ epoch ∥ ":" ∥ prev_hash[:32] )
```

The DAG is **epoch-stable**: miners within the same epoch share the same DAG. This allows pre-generation and caching but still requires full RAM allocation.

### DAG Size per Epoch

| Epoch | DAG Size | Min RAM |
|-------|----------|---------|
| 0     | 2 GB     | 4 GB    |
| 1     | 2.125 GB | 5 GB    |
| 2     | 2.25 GB  | 6 GB    |
| 5     | 2.625 GB | 9 GB    |
| 10    | 3.25 GB  | 14 GB   |

Epoch interval: **100,000 blocks** (~34.7 days at 30s block time).

---

## 4. Random Memory Walk

The core PoW operation. Each step:

1. Compute `pos = int(H[:8], little-endian) % DAG_size`
2. Read 32 bytes from `DAG[pos]`
3. `H_new = sha3_256(H_prev ∥ DAG[pos])`
4. Measure access time in nanoseconds
5. Repeat 100,000 times

Properties:
- **Unpredictable access**: each address depends on the previous hash result
- **No prefetch**: hardware prefetch cannot anticipate next address
- **Cache-defeating**: 2+ GB DAG far exceeds L1/L2/L3 cache
- **Sequential dependency**: steps cannot be parallelized

---

## 5. Legacy Boost System

PoLM-X applies a multiplier based on detected RAM generation. Older RAM is physically slower (higher latency), so the protocol rewards this inherent disadvantage:

| RAM Type | Multiplier | Rationale |
|----------|-----------|-----------|
| DDR2     | **2.20×** | ~80–200ns latency — maximum legacy bonus |
| DDR3     | **1.60×** | ~50–100ns latency — strong legacy bonus |
| DDR4     | **1.00×** | ~30–70ns latency — baseline |
| DDR5     | **0.85×** | ~20–50ns latency — modern penalty |

RAM type is detected via `dmidecode` (Linux) or OS API, preventing spoofing.

---

## 6. Saturation Penalty

High thread counts provide diminishing returns and are penalized:

| Threads | Penalty |
|---------|---------|
| 1–4     | 1.00×   |
| 5–8     | 0.90×   |
| 9–16    | 0.80×   |
| 17+     | 0.70×   |

This discourages large multi-socket server mining rigs and keeps single-socket legacy hardware competitive.

### Final Score Formula

```
score = work_units × legacy_boost × saturation_penalty
```

---

## 7. Block Structure

```
Block {
    height         : uint64
    prev_hash      : sha3-256 hex (64 chars)
    timestamp      : unix seconds
    nonce          : uint64
    miner_id       : string (address)
    ram_type       : DDR2 | DDR3 | DDR4 | DDR5
    thread_count   : uint8
    epoch          : uint32
    difficulty     : uint8  (leading zero nibbles)
    dag_seed       : sha3-256 hex
    latency_proof  : float (avg ns per access)
    memory_proof   : sha3-256 hex (final walk hash)
    score          : float
    transactions   : [ Transaction ]
    block_hash     : sha3-256( header_bytes ∥ tx_json )
}
```

---

## 8. Security Analysis

### 8.1 Anti-ASIC
- DAG grows each epoch — custom chips need large, re-flashable DRAM arrays
- Latency is **physical** — cannot be compressed on silicon
- Access pattern is unpredictable — cannot pipeline memory reads
- Hash chain prevents parallelism — each step depends on previous

### 8.2 Anti-GPU
GPUs have high memory bandwidth but **higher DRAM latency** (GDDR6: ~80–120ns). The latency-hard constraint neutralizes bandwidth advantage.

### 8.3 Anti-Cache Exploit
If all accesses resolve from cache (< 5ns avg), the latency proof fails validation and the block is rejected by all honest nodes.

### 8.4 Anti-Fake RAM
`dmidecode` reads SPD (Serial Presence Detect) chips directly on the DIMM. These cannot be spoofed in software. RAMDisk systems will exhibit anomalously low latency and fail the proof threshold.

### 8.5 Anti-Replay
Each block commits to `prev_hash`, `timestamp`, `nonce`, and `miner_id`. Replaying a valid block is impossible because the chain tip changes.

### 8.6 Anti-Fork (rapid fork attack)
The network enforces:
- Monotonic timestamps
- Height sequence validation
- Difficulty continuity

---

## 9. Economics

| Parameter     | Value                        |
|---------------|------------------------------|
| Symbol        | POLM                         |
| Max Supply    | 32,000,000 (32-bit era tribute) |
| Block Time    | 30 seconds                   |
| Initial Reward | 5.0 POLM                    |
| Halving       | Every 4 years (~4,204,800 blocks) |
| Difficulty Retarget | Every 144 blocks       |
| Retarget Window | ±25% per window            |

### Supply Schedule

| Year | Reward | Cumulative Supply |
|------|--------|------------------|
| 1    | 5.0    | ~5.25M           |
| 4    | 5.0    | ~21M             |
| 5    | 2.5    | ~22.3M           |
| 8    | 2.5    | ~24.7M           |
| 12   | 1.25   | ~27.5M           |

---

## 10. Expected Mining Competitiveness

Approximate relative performance (normalized to DDR4 i5 = 1.0):

| Hardware               | Score Multiplier | Notes |
|------------------------|-----------------|-------|
| Core 2 Duo + DDR2      | ~1.76×          | Very competitive |
| Athlon II + DDR3       | ~1.28×          | Competitive |
| i5 2nd gen + DDR3      | ~1.44×          | Good |
| i5 8th gen + DDR4      | ~1.00×          | Baseline |
| Ryzen 9 + DDR5 (16c)   | ~0.60×          | Heavy penalty |
| Xeon 32c + DDR4        | ~0.70×          | Thread penalty |

Max advantage of modern over legacy: **~2–3×** (vs. 20–100× in SHA-256 or Ethash).

---

## 11. Network Components

| Component | File | Description |
|-----------|------|-------------|
| Core Engine | `polm_x_core.py` | DAG, walk, chain, miner |
| Node | `polm_x_node.py` | P2P + REST API |
| Wallet | `polm_x_wallet.py` | ECDSA keys + signing |
| Explorer | `polm_x_explorer.py` | Web UI |

---

## 12. Comparison to PoLM v1

| Feature | PoLM v1 | PoLM-X v2 |
|---------|---------|-----------|
| Memory constraint | RAM minimum | RAM size + latency |
| DAG | Basic | Epoch-growing, hash-expanded |
| Latency proof | Measured | Measured + block-embedded + validated |
| Block structure | Basic | Full header with memory/latency proofs |
| Wallet | Basic | ECDSA secp256k1 |
| Explorer | Flask basic | Full retro-terminal UI |
| Anti-fake-RAM | dmidecode | dmidecode + latency threshold |
| Difficulty | Simple | LWMA-style ±25% cap |

---

## 13. Roadmap

- **v2.0** — Testnet: core engine, node, wallet, explorer ✓
- **v2.1** — P2P gossip protocol (libp2p-style)
- **v2.2** — SPV light client
- **v2.3** — Multi-threaded parallel mining (per-nonce DAG walk)
- **v3.0** — Mainnet genesis

---

*PoLM-X is experimental software. Testnet only. Not financial advice.*

**Repository**: https://github.com/proof-of-legacy/Proof-of-Legacy-Memory
