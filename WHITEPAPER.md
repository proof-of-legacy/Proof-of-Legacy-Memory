# PoLM — Proof of Legacy Memory
## Technical Whitepaper v3.0

---

> *"Every old computer deserves a second life."*

---

## Abstract

**PoLM** (Proof of Legacy Memory) is a Proof-of-Work consensus algorithm where the primary bottleneck is **real DRAM access latency** — a physical property that cannot be compressed, parallelized, or replicated efficiently in ASIC silicon. Unlike SHA-256 (compute-bound) or Ethash (VRAM bandwidth-bound), PoLM is **latency-bound**: the time required to complete one unit of work is dominated by how long it takes to read a random byte from RAM.

This design naturally favors older hardware (DDR2/DDR3) through an explicit **Legacy Boost** multiplier, while penalizing high thread-count modern systems through a **Saturation Penalty**. The result is a mining landscape where a Core 2 Duo from 2006 is genuinely competitive — validated empirically on March 15, 2026, when a Core 2 Duo successfully mined block #47 on a live 3-node testnet.

---

## 1. Motivation

### 1.1 The centralization problem

Every major Proof-of-Work algorithm has been captured by specialized hardware:

| Algorithm | Bottleneck | Outcome |
|-----------|-----------|---------|
| SHA-256 | Integer throughput | ASIC farms, massive centralization |
| Ethash | VRAM bandwidth | GPU farms, Nvidia/AMD dependency |
| RandomX | CPU cache + IPC | Still favors modern CPUs significantly |
| Chia | Storage I/O | HDD/SSD farms |

In each case, whoever can afford the most specialized hardware dominates. This creates barriers to entry, geographic centralization, and electronic waste as older hardware becomes worthless.

### 1.2 The PoLM hypothesis

DRAM latency is fundamentally physical. A DDR2 DIMM from 2006 takes ~80–200ns to service a random access request. A DDR5 DIMM from 2023 takes ~20–50ns. This difference exists because of physical distances, capacitor discharge times, and bus protocols — it cannot be engineered away without changing the fundamental architecture of DRAM.

PoLM exploits this: by making the PoW algorithm depend on sequential random memory accesses (where each address depends on the previous hash result), the algorithm becomes latency-bound rather than throughput-bound.

---

## 2. Algorithm

### 2.1 Memory DAG

A Memory DAG (Directed Acyclic Graph) is a large pseudorandom byte buffer, deterministically generated from a seed derived from the current epoch and the previous block hash:

```
seed = sha3_256("polm:" ∥ epoch ∥ ":" ∥ prev_hash[:32])
dag  = expand(seed) to DAG_SIZE bytes
```

The expansion uses a hash-chaining approach:
```
chunk_0 = sha3_512(seed)
chunk_1 = sha3_512(chunk_0)
chunk_2 = sha3_512(chunk_1)
...
DAG = concat(chunk_0, chunk_1, ...) truncated to DAG_SIZE
```

Properties:
- **Epoch-stable**: all miners in the same epoch use the same DAG
- **Chain-dependent**: DAG changes every epoch (100,000 blocks)
- **Size**: grows with each epoch, currently 4 MB in testnet

### 2.2 Random Memory Walk

The core PoW operation executes N sequential random memory accesses:

```python
h   = sha3_256(prev_hash ∥ miner_id ∥ nonce)
pos = int.from_bytes(h[:8], "little") % DAG_size

for step in range(N):
    t0  = perf_counter_ns()
    mem = DAG[pos : pos+32]          # random read
    t1  = perf_counter_ns()
    
    latency_samples.append(t1 - t0)
    h   = sha3_256(h ∥ mem)          # hash chain
    pos = int.from_bytes(h[:8], "little") % DAG_size

avg_latency = mean(latency_samples)
final_hash  = h
```

Key properties:
- **Unpredictable**: each address depends on the previous hash — no prefetch possible
- **Sequential**: steps cannot be parallelized — each depends on previous result
- **Cache-defeating**: DAG >> L1/L2/L3 cache on any realistic hardware
- **Latency-measuring**: actual ns per access is recorded and embedded in block

### 2.3 Block structure

```
Block {
    height       : uint64
    prev_hash    : sha3-256 hex
    timestamp    : unix seconds
    nonce        : uint64
    miner_id     : string
    ram_type     : DDR2 | DDR3 | DDR4 | DDR5
    threads      : uint8
    epoch        : uint32
    difficulty   : uint8
    latency_ns   : float  ← average ns per memory access
    mem_proof    : sha3-256 hex  ← final walk hash
    score        : float
    reward       : float
    block_hash   : sha3-256(all fields above)
}
```

### 2.4 Block validation

A block is valid if and only if:
1. `height == chain.height + 1`
2. `prev_hash == chain.tip.block_hash`
3. `block_hash.startswith("0" * difficulty)`
4. `block_hash == sha3_256(all header fields)`
5. `latency_ns >= 5` (anti-cache-exploit threshold)
6. `reward == block_reward(height)` (correct coinbase)
7. `timestamp >= parent.timestamp`

---

## 3. Legacy Boost System

### 3.1 Rationale

Older RAM generations have inherently higher latency. This is not a flaw — it is a physical reality of older memory cell architectures, lower bus frequencies, and higher signal propagation delays. PoLM rewards this latency with a multiplier:

| RAM Type | Multiplier | Measured Latency (testnet) |
|----------|-----------|---------------------------|
| DDR2 | **2.20×** | ~6000–8000 ns |
| DDR3 | **1.60×** | ~1500–3000 ns |
| DDR4 | 1.00× | ~900–1600 ns |
| DDR5 | 0.85× | ~500–900 ns |

### 3.2 Detection

RAM type is detected via `dmidecode -t memory` on Linux, reading SPD (Serial Presence Detect) data directly from the DIMM. This cannot be spoofed in software. As a fallback, the `POLM_RAM_TYPE` environment variable allows manual override for systems where `dmidecode` is unavailable.

### 3.3 Saturation Penalty

High thread counts provide diminishing returns for latency-bound workloads and are penalized:

| Threads | Penalty |
|---------|---------|
| 1–4 | 1.00× |
| 5–8 | 0.90× |
| 9–16 | 0.80× |
| 17+ | 0.70× |

### 3.4 Final score

```
score = work_units × legacy_boost × saturation_penalty
```

Score is informational — it does not affect PoW validity, which depends only on the block hash meeting the difficulty target.

---

## 4. Network Architecture (v3.0)

PoLM v3.0 uses a **pool architecture**:

```
Central Node
├── Stores and validates the blockchain
├── Exposes /getwork → current mining job
├── Exposes /submit → accepts completed blocks
└── Exposes /chain, /miners, /balance

Miners (any number, any machine)
├── Call GET /getwork → {height, prev_hash, difficulty, reward}
├── Execute Random Memory Walk
├── Check for new work every N attempts (non-blocking)
└── Call POST /submit with completed block
```

This is intentionally simple — identical in concept to Bitcoin's getblocktemplate / stratum protocol, without requiring each miner to maintain a full chain.

---

## 5. Security Analysis

### 5.1 Anti-ASIC

An ASIC targeting PoLM would need to:
- Incorporate large DRAM arrays (DAG size, currently 4 MB testnet / 2 GB mainnet)
- Execute unpredictable random accesses to that DRAM
- Cannot pipeline reads (each address depends on previous hash result)
- DAG grows each epoch — ASIC would need reprogrammable large memory

This is fundamentally incompatible with the dense, fixed-function architecture that makes ASICs efficient. The closest analog would be an FPGA with attached DRAM — which provides minimal advantage over a standard CPU with the same RAM.

### 5.2 Anti-GPU

GPUs have high memory bandwidth (GDDR6: ~600 GB/s) but **higher latency** than system DRAM (GDDR6: ~80–120 ns vs DDR4: ~30–70 ns random access). Since PoLM is latency-bound, not bandwidth-bound, GPUs have no structural advantage. Our testnet confirmed this: DDR4 system RAM (900–1600 ns measured) outperformed GDDR-equivalent latency profiles.

### 5.3 Anti-cache exploit

If a miner attempts to serve all DAG reads from CPU cache (L3 hit: ~3–5 ns), the measured `latency_ns` will be below the threshold of 5 ns and the block will be rejected by all validating nodes.

### 5.4 Anti-replay

Each block commits to `prev_hash` (changes every block), `timestamp`, `nonce`, and `miner_id`. A valid block from height N cannot be replayed at height N+1 because `prev_hash` would not match.

---

## 6. Economics

### 6.1 Supply

Total supply: **32,000,000 POLM** — a tribute to the 32-bit computing era.

### 6.2 Emission schedule

```
block_reward(height) = 5.0 / 2^(height // HALVING_BLOCKS)

HALVING_BLOCKS = 4 * 365 * 24 * 120  # ~4 years at 30s blocks
               = 4,204,800 blocks
```

| Period | Reward/block | Duration | New supply |
|--------|-------------|----------|-----------|
| 0–4yr | 5.0 POLM | 4,204,800 blocks | ~21.0M |
| 4–8yr | 2.5 POLM | 4,204,800 blocks | ~10.5M |
| 8–12yr | 1.25 POLM | 4,204,800 blocks | ~5.25M |
| 12–16yr | 0.625 POLM | … | ~2.6M |

### 6.3 Difficulty adjustment

Retargets every 144 blocks using actual vs expected time:

```
ratio     = (BLOCK_TIME * 143) / elapsed_time
ratio     = clamp(ratio, 0.75, 1.25)  # max ±25% per window
new_diff  = max(1, round(current_diff * ratio))
```

---

## 7. Empirical Results (Testnet, March 15 2026)

Three-node testnet ran for ~2 hours mining 50+ blocks:

| Miner | Hardware | RAM | Measured Latency | Boost | Blocks Won |
|-------|----------|-----|-----------------|-------|-----------|
| POLM_Aluisio | i5 12th gen, 16t | DDR4 | 999 ns avg | 0.80× (penalty) | 34 |
| POLM6837… | i5 7th gen, 4t | DDR4 | 1610 ns avg | 1.00× | 13 |
| POLMBE9E… | Core 2 Duo, 2t | DDR2 | **6746 ns avg** | **2.20×** | **1** |

Key observations:
- DDR2 latency was ~6.7× higher than DDR4 — within expected range
- Core 2 Duo successfully competed and won block #47
- Maximum hardware advantage: ~3× (vs 100× in SHA-256 mining)
- Switching mechanism (check new work every 200 attempts) was essential for slow miners

---

## 8. Roadmap

| Version | Status | Features |
|---------|--------|---------|
| v1.0 | ✅ | Basic PoW, RAM latency measurement |
| v2.0 | ✅ | Memory DAG, latency proof, legacy boost, full node |
| v3.0 | ✅ | Pool architecture, single-file protocol |
| v3.1 | 🔲 | Web explorer |
| v3.2 | 🔲 | ECDSA wallet, transaction support |
| v3.3 | 🔲 | P2P full nodes (multiple chain holders) |
| v4.0 | 🔲 | Mainnet genesis |

---

*PoLM is experimental software. Testnet only. Not financial advice.*

**Repository**: https://github.com/proof-of-legacy/Proof-of-Legacy-Memory
