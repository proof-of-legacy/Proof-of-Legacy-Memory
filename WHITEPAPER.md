# PoLM — Proof of Legacy Memory
## Technical Whitepaper v2.0 — Mainnet

<div align="center">

**https://polm.com.br**  
[@polm2026](https://x.com/polm2026) · [@aluisiofer](https://x.com/aluisiofer)

</div>

---

> *"Mine with any RAM. Latency is truth."*

---

## Abstract

**PoLM** (Proof of Legacy Memory) is a Proof-of-Work consensus algorithm where the primary bottleneck is **real DRAM access latency** — a physical property that cannot be miniaturized, parallelized, or replicated in ASIC silicon.

Unlike SHA-256 (compute-bound) or Ethash (VRAM bandwidth-bound), PoLM is **latency-bound**: the time to complete one unit of work is dominated by how long it takes to read random bytes from RAM.

The score formula is:

```
score = 1 / latency_ns
```

No boost multiplier. No penalty. No artificial favoritism by RAM type. Every generation — DDR2, DDR3, DDR4, DDR5 — mines honestly based on its physical latency characteristics. Slower RAM scores higher per nonce; faster RAM compensates with higher nonce throughput. The network needs both.

---

## 1. Project Information

| Field | Value |
|-------|-------|
| Project name | PoLM — Proof of Legacy Memory |
| Symbol | POLM |
| Version | 2.0.0 |
| Website | https://polm.com.br |
| Explorer | https://explorer.polm.com.br |
| Twitter | https://x.com/polm2026 |
| Founder | Aluísio Fernandes — https://x.com/aluisiofer |
| Repository | https://github.com/proof-of-legacy/Proof-of-Legacy-Memory |
| License | MIT |
| Status | Mainnet live |

---

## 2. Objectives

- Support any RAM generation — DDR2 through DDR5 and beyond
- Be fully decentralized — no central authority, no pool required
- Resist ASICs naturally via DRAM physics
- Drive a new hardware upgrade cycle through epoch-based DAG growth
- Maintain honest competition across all RAM generations
- Create a new hardware market by Epoch 7 (1 TB RAM arrays)

---

## 3. Protocol Parameters

| Parameter | Value |
|-----------|-------|
| Block Time Target | 120 seconds (2 minutes) |
| Difficulty Window | 144 blocks |
| Difficulty Clamp | ±25% per window |
| Epoch Length | 100,000 blocks (~138 days) |
| Initial Reward | 50.0 POLM |
| Halving Interval | 100,000 blocks per epoch |
| Max Supply | 210,000,000 POLM |
| Hash Algorithm | SHA3-256 |
| Score Formula | 1 / latency_ns |
| DAG (Epoch 0) | 256 MB |
| DAG Growth | doubles each epoch |
| Walk Steps | 100,000 per nonce |
| Max Threads | 4 per miner |
| Min Transaction Fee | 0.0001 POLM |

---

## 4. Network Architecture

```
┌──────────────────────────────────────────────┐
│           Full Nodes (Consensus)             │
│  Validate blocks · Store chain · REST API    │
│  polm.com.br/api/                            │
└──────────────┬───────────────────────────────┘
               │
        ┌──────┴──────┐
        ▼             ▼
  Relay Nodes    Mining Clients
                      │
    DDR2 ── DDR3 ── DDR4 ── DDR5
             Any RAM mines
```

---

## 5. PoLM Algorithm

### Flow

```
1. Generate Memory DAG (256 MB in Epoch 0, seeded from epoch + prev_hash)
2. Initialize hash from: prev_hash + miner_address + nonce
3. Execute random memory walk (100,000 steps)
4. Measure average access latency (ns)
5. Compute score = 1 / latency_ns
6. Validate: block_hash must start with "0" × difficulty
```

### Memory Walk

```python
h   = sha3_256(prev_hash + address + nonce)
pos = int(h[:8], little_endian) % dag_size

for step in range(100_000):
    mem = DAG[pos : pos+32]           # random DRAM read
    h   = sha3_256(h + mem)           # hash chain
    pos = int(h[:8], little_endian) % dag_size
    record_latency(read_time_ns)

avg_latency = total_ns / 100_000
score       = 1.0 / avg_latency
final_hash  = h
```

Properties:
- **Unpredictable access pattern** — CPU prefetch cannot help
- **Sequential dependency** — cannot parallelize steps
- **Cache-defeating** — 256 MB DAG >> any L1/L2/L3 cache
- **Tamper-proof** — latency is measured and embedded in block header

---

## 6. Score Formula

```
score = 1 / latency_ns
```

This is the complete formula. No multipliers. No lookup tables. No penalties.

### Why this is fair

| RAM | Avg Latency | Score/nonce | Nonces/sec | Result |
|-----|-------------|-------------|------------|--------|
| DDR2 | ~3800 ns | high | low | high score per nonce |
| DDR3 | ~2000 ns | medium | medium | balanced |
| DDR4 | ~1200 ns | lower | higher | more nonces |
| DDR5 | ~600 ns | lowest | highest | maximum throughput |

Slower RAM does more work per step. Faster RAM processes more steps per second. The network receives honest work from all generations.

---

## 7. Difficulty Adjustment

```python
expected_time = 144 × 120 = 17,280 seconds
actual_time   = Δt of last 144 blocks

ratio = clamp(0.75, 1.25, expected_time / actual_time)
D_new = D_old × ratio
```

Adjusts every 144 blocks. Maximum ±25% change per window prevents oscillation. Target: one block every 2 minutes.

---

## 8. Memory DAG

```python
dag_seed = sha3_256("polm:" + str(epoch) + ":" + prev_hash[:32])
dag_size = 256 * (2 ** epoch)  # MB — doubles each epoch
```

The DAG doubles each epoch. This prevents caching across epochs and increases RAM requirements over time — the core mechanism driving hardware evolution.

---

## 9. Epoch Schedule

Every 100,000 blocks (~138 days at 2 min/block):
- DAG seed changes (new epoch + prev_hash)
- DAG doubles in size
- Block reward halves
- Minimum RAM requirement increases

```python
epoch  = height // 100_000
reward = 50.0 / (2 ** epoch)
```

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

> **Epoch 0 is the most accessible window.** Any machine with 4 GB+ RAM — DDR2 to DDR5 — can mine today.

---

## 10. Block Validation Rules

A block is valid if ALL of the following hold:

```
1. block_hash starts with "0" × difficulty
2. block_hash == sha3_256(all_header_fields)
3. height == chain.tip.height + 1
4. prev_hash == chain.tip.block_hash
5. latency_ns >= 5  (anti-cache-exploit)
6. reward == 50.0 / (2 ** epoch)  (epoch halving enforced)
7. timestamp <= now + 120  (±2 min tolerance)
8. ram_size_mb >= MIN_RAM_MB[epoch]
```

---

## 11. Transactions

### Transaction format

```
tx_id     = sha3_256(signing_bytes + signature)
signing   = "sender:receiver:amount:fee:timestamp:memo"
signature = ECDSA secp256k1
```

### Transaction validation

```
1. amount > 0
2. fee >= 0.0001 POLM
3. sender.balance >= amount + fee
4. signature valid (ECDSA secp256k1)
5. not already confirmed
6. addresses start with "POLM"
```

---

## 12. Wallet Standard

| Parameter | Value |
|-----------|-------|
| HD wallet | BIP-39 / BIP-44 |
| Mnemonic | 24 words |
| Derivation path | m/44'/7070'/account'/0/index |
| Address prefix | POLM |
| Signature | ECDSA secp256k1 |
| Coin type | SLIP-44 #7070 |

---

## 13. Security Model

| Attack | Defense |
|--------|---------|
| ASIC | 256 MB+ DAG + sequential walk — DRAM physics are irreducible |
| GPU | GDDR latency ≥ DDR latency — no systematic advantage |
| Cache exploit | Latency < 5 ns → block rejected by consensus |
| Fake latency | Score is computed from measured reads, not declared type |
| Timestamp manipulation | ±120s tolerance enforced |
| Double spend | Longest chain rule, fast propagation |
| 51% attack | Requires >50% of total latency-weighted hashrate |

**ASIC resistance:** The gap between DDR2 (~3800 ns) and DDR5 (~600 ns) is ~6×. In SHA-256, ASICs are 100,000× faster than CPUs. PoLM's physical constraint means custom silicon has no useful advantage — DRAM latency cannot be engineered away.

---

## 14. Economics

### Token parameters

| Parameter | Value |
|-----------|-------|
| Symbol | POLM |
| Max supply | 210,000,000 |
| Block reward (Epoch 0) | 50 POLM |
| Block time | 2 minutes |
| Halving | every epoch (100,000 blocks, ~138 days) |
| Pre-mine / ICO | None |
| Founder allocation | 5% · locked 5 years |

### Emission schedule

| Epoch | Reward | ~POLM minted |
|-------|--------|-------------|
| 0 | 50 POLM | 5,000,000 |
| 1 | 25 POLM | 2,500,000 |
| 2 | 12.5 POLM | 1,250,000 |
| 3 | 6.25 POLM | 625,000 |
| 4 | 3.125 POLM | 312,500 |
| … | halving | → 210M total |

Full supply takes **30+ years** to mine completely. Emission is predictable and manipulation-resistant.

### Participant incentives

| Participant | Revenue |
|-------------|---------|
| Miners | Block rewards + transaction fees |
| Full nodes | Network infrastructure (public good) |

---

## 15. Founder Allocation

| Parameter | Value |
|-----------|-------|
| Founder | Aluísio Fernandes (@aluisiofer) |
| Allocation | 10,500,000 POLM (5% of max supply) |
| Lock period | 5,256,000 blocks (~5 years) |
| Address | POLMD872771E5F0017C5B5C08D353B5E7B4B |

Enforced at consensus level — no transaction from the founder address is valid before the lock expires:

```python
if tx.sender == FOUNDER_ADDRESS:
    assert current_height >= GENESIS_HEIGHT + 5_256_000
```

---

## 16. REST API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Node status + chain summary |
| `/getwork` | GET | Mining job |
| `/submit` | POST | Submit mined block |
| `/tx/send` | POST | Broadcast transaction |
| `/chain` | GET | Block list (?limit=N&offset=N) |
| `/block/<h>` | GET | Block + transactions |
| `/balance/<addr>` | GET | Address balance |
| `/miners` | GET | Mining leaderboard |
| `/peers` | GET | Connected peers |

---

## 17. Technology Stack

| Component | Current |
|-----------|---------|
| Full Node | Python + Flask |
| Miner | Python |
| Explorer | Python + Flask (v2.2.0) |
| Wallet | Python + HTML/JS |
| Database | JSON files |
| API | REST / JSON |

---

## 18. Roadmap

- [x] v1.0 — PoLM algorithm designed and tested
- [x] v1.2 — Mainnet infrastructure · polm.com.br
- [x] v2.0 — Pure latency consensus · any RAM mines · epoch halving ← **current**
- [ ] v2.1 — One-click miner UI (Windows .exe)
- [ ] Bridge — Polygon DEX · POLMTokenV2 (~$0.001/tx)
- [ ] Trust Wallet / MetaMask integration
- [ ] CoinMarketCap / CoinGecko listing
- [ ] Epoch 7 — 1 TB RAM mining arrays (new hardware market)

---

## 19. Conclusion

PoLM introduces a fundamentally new class of Proof-of-Work grounded in DRAM physics. By making latency — not compute power — the bottleneck:

1. **Any RAM mines** — DDR2 through DDR5, all generations participate honestly
2. **No artificial rules** — score = 1/latency_ns, nothing else
3. **ASIC-resistant by physics** — DRAM latency cannot be engineered away
4. **Hardware evolution is built-in** — epochs force RAM upgrade cycles, creating a new industry by Epoch 7
5. **Truly decentralized** — any PC with 4 GB+ RAM mines in Epoch 0

The network grows more demanding over time — not through arbitrary rules, but through the natural physics of memory access and the doubling of the DAG. This creates an organic, predictable hardware evolution cycle unprecedented in Proof-of-Work history.

---

*PoLM is experimental software. Not financial advice.*  
*Website: https://polm.com.br*  
*Twitter: https://x.com/polm2026*  
*Founder: https://x.com/aluisiofer*  
*MIT License · © 2026 Aluísio Fernandes (Aluminium)*
