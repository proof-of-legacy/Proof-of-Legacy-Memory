"""
PoLM-X v2 — Proof of Legacy Memory (Extended)
Memory-Hard + Latency-Hard Consensus Algorithm
Blockchain core engine — ultra-strong legacy-first PoW
"""

import hashlib
import time
import json
import os
import struct
import random
import threading
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Tuple
from enum import Enum

# ─────────────────────────────────────────────
# PROTOCOL CONSTANTS
# ─────────────────────────────────────────────
POLM_VERSION         = "2.0.0"
COIN_SYMBOL          = "POLM"
BLOCK_TIME_TARGET    = 30          # seconds
INITIAL_REWARD       = 5.0         # POLM per block
MAX_SUPPLY           = 32_000_000  # 32 million — 32-bit era tribute
HALVING_BLOCKS       = 4 * 365 * 24 * 120  # ~4 years @ 30s blocks
DIFFICULTY_WINDOW    = 144         # blocks for retarget
EPOCH_BLOCKS         = 100_000     # blocks per memory epoch
DAG_INITIAL_MB       = 2048        # 2 GB initial DAG
DAG_GROWTH_MB        = 128         # growth per epoch
MEMORY_WALK_STEPS    = 100_000     # accesses per mining cycle
HASH_ALGO            = "sha3_256"
GENESIS_TIMESTAMP    = 1741000000  # fixed genesis time
NETWORK_MAGIC        = b"\xPO\xLM"

# ─────────────────────────────────────────────
# RAM TYPE CLASSIFICATION
# ─────────────────────────────────────────────
class RAMType(Enum):
    DDR2 = "DDR2"
    DDR3 = "DDR3"
    DDR4 = "DDR4"
    DDR5 = "DDR5"
    UNKNOWN = "UNKNOWN"

LEGACY_BOOST: Dict[RAMType, float] = {
    RAMType.DDR2:    2.20,
    RAMType.DDR3:    1.60,
    RAMType.DDR4:    1.00,
    RAMType.DDR5:    0.85,
    RAMType.UNKNOWN: 1.00,
}

# ─────────────────────────────────────────────
# SATURATION PENALTY (thread count)
# ─────────────────────────────────────────────
def saturation_penalty(threads: int) -> float:
    if threads <= 4:  return 1.0
    if threads <= 8:  return 0.9
    if threads <= 16: return 0.8
    return 0.7

# ─────────────────────────────────────────────
# EPOCH LOGIC
# ─────────────────────────────────────────────
def get_epoch(block_height: int) -> int:
    return block_height // EPOCH_BLOCKS

def get_min_ram_mb(epoch: int) -> int:
    """Minimum RAM in MB required for given epoch."""
    return 4096 + (epoch * 1024)  # 4 GB + 1 GB per epoch

def get_dag_size_mb(epoch: int) -> int:
    """DAG size in MB for given epoch."""
    return DAG_INITIAL_MB + (epoch * DAG_GROWTH_MB)

# ─────────────────────────────────────────────
# HARDWARE DETECTION
# ─────────────────────────────────────────────
def detect_ram_type() -> RAMType:
    """Try to detect RAM type via dmidecode (Linux) or fallback."""
    try:
        import subprocess
        result = subprocess.run(
            ["dmidecode", "-t", "memory"],
            capture_output=True, text=True, timeout=5
        )
        output = result.stdout.lower()
        if "ddr5" in output: return RAMType.DDR5
        if "ddr4" in output: return RAMType.DDR4
        if "ddr3" in output: return RAMType.DDR3
        if "ddr2" in output: return RAMType.DDR2
    except Exception:
        pass
    # Fallback: use environment variable override
    env_ram = os.environ.get("POLM_RAM_TYPE", "").upper()
    for r in RAMType:
        if r.value == env_ram:
            return r
    return RAMType.UNKNOWN

def get_cpu_threads() -> int:
    return os.cpu_count() or 1

# ─────────────────────────────────────────────
# MEMORY DAG
# ─────────────────────────────────────────────
class MemoryDAG:
    """
    Memory DAG: large byte buffer seeded from block seed.
    Simulates full DAG with a compact representation for testnet.
    Production: allocates full DAG_SIZE in RAM.
    """
    TESTNET_DAG_MB = 4  # use 4 MB in testnet for speed

    def __init__(self, seed: bytes, epoch: int, testnet: bool = True):
        self.seed    = seed
        self.epoch   = epoch
        self.testnet = testnet
        size_mb      = self.TESTNET_DAG_MB if testnet else get_dag_size_mb(epoch)
        self.size    = size_mb * 1024 * 1024
        self._build()

    def _build(self) -> None:
        """Fill DAG buffer deterministically from seed."""
        h = hashlib.sha3_256(self.seed).digest()
        # For testnet: generate pseudorandom DAG via hash expansion
        chunks = []
        needed = self.size
        current = h
        while needed > 0:
            block = hashlib.sha3_512(current).digest()  # 64 bytes
            chunks.append(block)
            needed -= len(block)
            current = block
        self._buf = bytearray(b"".join(chunks)[:self.size])

    def read(self, pos: int) -> bytes:
        """Read 32 bytes from DAG at position."""
        idx = (pos % (self.size - 32))
        return bytes(self._buf[idx:idx+32])

    def read_int(self, pos: int) -> int:
        data = self.read(pos)
        return int.from_bytes(data[:8], "little")

# ─────────────────────────────────────────────
# LATENCY MEASUREMENT
# ─────────────────────────────────────────────
def measure_memory_latency(dag: MemoryDAG, samples: int = 1000) -> float:
    """
    Measure average random access latency on DAG in nanoseconds.
    Used for latency proof and anti-fake-RAM detection.
    """
    total = 0.0
    pos = 0
    for _ in range(samples):
        t0 = time.perf_counter_ns()
        val = dag.read_int(pos)
        t1 = time.perf_counter_ns()
        total += (t1 - t0)
        pos = (val % dag.size)
    return total / samples

def latency_is_valid(latency_ns: float, ram_type: RAMType) -> bool:
    """
    Validate that measured latency is consistent with declared RAM type.
    Rough thresholds (ns):
      DDR2:  ~80–200 ns typical random access
      DDR3:  ~50–100 ns
      DDR4:  ~30–70  ns
      DDR5:  ~20–50  ns
    We are generous to allow virtualization overhead.
    Returns False only if latency is impossibly fast (cache exploit).
    """
    if latency_ns < 5:
        return False  # impossibly fast — cache hit, not RAM
    return True

# ─────────────────────────────────────────────
# RANDOM MEMORY WALK (core PoW)
# ─────────────────────────────────────────────
def random_memory_walk(
    dag: MemoryDAG,
    seed_hash: bytes,
    steps: int = MEMORY_WALK_STEPS
) -> Tuple[bytes, float]:
    """
    Execute random memory walk on DAG.
    Returns (final_hash, average_latency_ns).
    Each step: new_pos = H(prev_hash || dag[pos]) % dag_size
    """
    h = seed_hash
    pos = int.from_bytes(h[:8], "little") % dag.size
    total_latency = 0.0

    for _ in range(steps):
        t0 = time.perf_counter_ns()
        mem_val = dag.read(pos)
        t1 = time.perf_counter_ns()
        total_latency += (t1 - t0)

        # hash chain: depends on previous hash AND memory content
        h = hashlib.sha3_256(h + mem_val).digest()
        pos = int.from_bytes(h[:8], "little") % dag.size

    avg_latency = total_latency / steps
    return h, avg_latency

# ─────────────────────────────────────────────
# WORK SCORE
# ─────────────────────────────────────────────
def compute_score(
    work_units: int,
    ram_type: RAMType,
    thread_count: int
) -> float:
    lb = LEGACY_BOOST.get(ram_type, 1.0)
    sp = saturation_penalty(thread_count)
    return work_units * lb * sp

# ─────────────────────────────────────────────
# BLOCK STRUCTURE
# ─────────────────────────────────────────────
@dataclass
class BlockHeader:
    height:        int
    prev_hash:     str
    timestamp:     int
    nonce:         int
    miner_id:      str
    ram_type:      str
    thread_count:  int
    epoch:         int
    difficulty:    int
    dag_seed:      str   # hex seed used for DAG
    latency_proof: float # measured ns
    memory_proof:  str   # hex of final walk hash
    score:         float

    def to_bytes(self) -> bytes:
        data = (
            f"{self.height}|{self.prev_hash}|{self.timestamp}|"
            f"{self.nonce}|{self.miner_id}|{self.ram_type}|"
            f"{self.thread_count}|{self.epoch}|{self.difficulty}|"
            f"{self.dag_seed}|{self.latency_proof:.4f}|{self.memory_proof}|"
            f"{self.score:.6f}"
        )
        return data.encode()

    def hash(self) -> str:
        return hashlib.sha3_256(self.to_bytes()).hexdigest()

@dataclass
class Transaction:
    tx_id:      str
    sender:     str
    receiver:   str
    amount:     float
    fee:        float
    timestamp:  int
    signature:  str

    @classmethod
    def coinbase(cls, miner_id: str, reward: float, height: int) -> "Transaction":
        tx_id = hashlib.sha3_256(
            f"coinbase:{miner_id}:{height}:{reward}".encode()
        ).hexdigest()
        return cls(
            tx_id=tx_id,
            sender="COINBASE",
            receiver=miner_id,
            amount=reward,
            fee=0.0,
            timestamp=int(time.time()),
            signature="COINBASE"
        )

@dataclass
class Block:
    header:       BlockHeader
    transactions: List[Transaction] = field(default_factory=list)
    block_hash:   str = ""

    def __post_init__(self):
        if not self.block_hash:
            self.block_hash = self.compute_hash()

    def compute_hash(self) -> str:
        tx_data = json.dumps(
            [asdict(tx) for tx in self.transactions], sort_keys=True
        )
        raw = self.header.to_bytes() + tx_data.encode()
        return hashlib.sha3_256(raw).hexdigest()

    def to_dict(self) -> dict:
        d = asdict(self.header)
        d["transactions"] = [asdict(tx) for tx in self.transactions]
        d["block_hash"]   = self.block_hash
        return d

# ─────────────────────────────────────────────
# DIFFICULTY ENGINE
# ─────────────────────────────────────────────
class DifficultyEngine:
    """Retargets difficulty every DIFFICULTY_WINDOW blocks."""

    INITIAL_DIFFICULTY = 4  # leading hex zeros required

    def __init__(self):
        self._current = self.INITIAL_DIFFICULTY

    @property
    def current(self) -> int:
        return self._current

    def retarget(self, recent_blocks: List[Block]) -> int:
        if len(recent_blocks) < 2:
            return self._current
        window = recent_blocks[-DIFFICULTY_WINDOW:]
        if len(window) < 2:
            return self._current
        elapsed = window[-1].header.timestamp - window[0].header.timestamp
        expected = BLOCK_TIME_TARGET * (len(window) - 1)
        if elapsed == 0:
            return self._current
        ratio = expected / elapsed
        # clamp adjustment to ±25%
        ratio = max(0.75, min(1.25, ratio))
        new_diff = max(1, round(self._current * ratio))
        self._current = new_diff
        return new_diff

    def target_prefix(self) -> str:
        return "0" * self._current

# ─────────────────────────────────────────────
# REWARD ENGINE
# ─────────────────────────────────────────────
def block_reward(height: int) -> float:
    halvings = height // HALVING_BLOCKS
    if halvings >= 64:
        return 0.0
    return INITIAL_REWARD / (2 ** halvings)

# ─────────────────────────────────────────────
# BLOCKCHAIN
# ─────────────────────────────────────────────
class PoLMChain:
    """Main blockchain — stores blocks, validates, manages state."""

    def __init__(self, chain_file: str = "polmx_chain.json", testnet: bool = True):
        self.chain_file = chain_file
        self.testnet    = testnet
        self.chain: List[Block] = []
        self.difficulty = DifficultyEngine()
        self._lock = threading.Lock()
        self._load_or_genesis()

    # ── genesis ──────────────────────────────
    def _load_or_genesis(self):
        if os.path.exists(self.chain_file):
            self._load_chain()
        else:
            self._create_genesis()

    def _create_genesis(self):
        seed = hashlib.sha3_256(b"PoLM-X Genesis Block 2025").hexdigest()
        header = BlockHeader(
            height=0,
            prev_hash="0" * 64,
            timestamp=GENESIS_TIMESTAMP,
            nonce=0,
            miner_id="GENESIS",
            ram_type=RAMType.DDR4.value,
            thread_count=1,
            epoch=0,
            difficulty=self.difficulty.current,
            dag_seed=seed,
            latency_proof=0.0,
            memory_proof="0" * 64,
            score=0.0,
        )
        coinbase = Transaction.coinbase("GENESIS", INITIAL_REWARD, 0)
        genesis = Block(header=header, transactions=[coinbase])
        genesis.block_hash = genesis.compute_hash()
        self.chain.append(genesis)
        self._save_chain()
        print(f"[PoLM-X] Genesis block created: {genesis.block_hash[:16]}…")

    # ── persistence ──────────────────────────
    def _save_chain(self):
        with open(self.chain_file, "w") as f:
            json.dump([b.to_dict() for b in self.chain], f, indent=2)

    def _load_chain(self):
        with open(self.chain_file) as f:
            data = json.load(f)
        for bd in data:
            txs = [Transaction(**tx) for tx in bd.pop("transactions")]
            bh  = bd.pop("block_hash")
            header = BlockHeader(**bd)
            blk = Block(header=header, transactions=txs, block_hash=bh)
            self.chain.append(blk)
        print(f"[PoLM-X] Loaded chain: {len(self.chain)} blocks")

    # ── state ────────────────────────────────
    @property
    def height(self) -> int:
        return len(self.chain) - 1

    @property
    def tip(self) -> Block:
        return self.chain[-1]

    def get_balance(self, address: str) -> float:
        balance = 0.0
        for blk in self.chain:
            for tx in blk.transactions:
                if tx.receiver == address:
                    balance += tx.amount
                if tx.sender == address:
                    balance -= (tx.amount + tx.fee)
        return round(balance, 8)

    def total_supply(self) -> float:
        return sum(
            tx.amount
            for blk in self.chain
            for tx in blk.transactions
            if tx.sender == "COINBASE"
        )

    # ── validation ───────────────────────────
    def validate_block(self, blk: Block) -> Tuple[bool, str]:
        h = blk.header
        # 1. height sequence
        if h.height != self.height + 1:
            return False, f"invalid height {h.height}, expected {self.height+1}"
        # 2. previous hash
        if h.prev_hash != self.tip.block_hash:
            return False, "prev_hash mismatch"
        # 3. timestamp sanity
        now = int(time.time())
        if h.timestamp > now + 120:
            return False, "timestamp too far in future"
        if h.timestamp < self.tip.header.timestamp:
            return False, "timestamp before parent"
        # 4. PoW prefix
        if not blk.block_hash.startswith(self.difficulty.target_prefix()):
            return False, f"insufficient PoW: {blk.block_hash[:8]}…"
        # 5. hash integrity
        if blk.compute_hash() != blk.block_hash:
            return False, "block_hash mismatch"
        # 6. latency proof sanity
        if not latency_is_valid(h.latency_proof, RAMType(h.ram_type)):
            return False, f"invalid latency proof: {h.latency_proof:.1f}ns"
        # 7. epoch matches height
        expected_epoch = get_epoch(h.height)
        if h.epoch != expected_epoch:
            return False, f"epoch mismatch: got {h.epoch}, expected {expected_epoch}"
        # 8. coinbase reward
        reward = block_reward(h.height)
        coinbase_txs = [tx for tx in blk.transactions if tx.sender == "COINBASE"]
        if not coinbase_txs:
            return False, "missing coinbase"
        if abs(coinbase_txs[0].amount - reward) > 0.0001:
            return False, f"wrong coinbase reward: {coinbase_txs[0].amount} vs {reward}"
        return True, "ok"

    def add_block(self, blk: Block) -> Tuple[bool, str]:
        with self._lock:
            ok, reason = self.validate_block(blk)
            if not ok:
                return False, reason
            self.chain.append(blk)
            # retarget every window
            if len(self.chain) % DIFFICULTY_WINDOW == 0:
                self.difficulty.retarget(self.chain)
            self._save_chain()
            return True, "ok"

    def summary(self) -> dict:
        return {
            "version":      POLM_VERSION,
            "height":       self.height,
            "tip_hash":     self.tip.block_hash,
            "difficulty":   self.difficulty.current,
            "epoch":        get_epoch(self.height),
            "min_ram_mb":   get_min_ram_mb(get_epoch(self.height)),
            "dag_size_mb":  get_dag_size_mb(get_epoch(self.height)),
            "total_supply": round(self.total_supply(), 4),
            "max_supply":   MAX_SUPPLY,
            "next_reward":  block_reward(self.height + 1),
        }

# ─────────────────────────────────────────────
# MINER
# ─────────────────────────────────────────────
class PoLMXMiner:
    """
    PoLM-X miner implementing full Memory-Hard + Latency-Hard PoW.
    """

    def __init__(
        self,
        chain: PoLMChain,
        miner_id: str,
        ram_type: Optional[RAMType] = None,
        threads: Optional[int] = None,
        verbose: bool = True,
    ):
        self.chain    = chain
        self.miner_id = miner_id
        self.ram_type = ram_type or detect_ram_type()
        self.threads  = threads or get_cpu_threads()
        self.verbose  = verbose
        self._stop    = threading.Event()
        print(f"[Miner] ID={miner_id}  RAM={self.ram_type.value}  "
              f"Threads={self.threads}  "
              f"LegacyBoost={LEGACY_BOOST[self.ram_type]:.2f}x  "
              f"SatPenalty={saturation_penalty(self.threads):.2f}x")

    def _build_dag_seed(self, prev_hash: str, height: int) -> bytes:
        """DAG seed depends on block height and prev_hash (epoch-stable)."""
        epoch = get_epoch(height)
        seed_str = f"polmx:{epoch}:{prev_hash[:32]}"
        return hashlib.sha3_256(seed_str.encode()).digest()

    def mine_block(
        self,
        pending_txs: Optional[List[Transaction]] = None
    ) -> Optional[Block]:
        """
        Mine one block. Returns Block when found, None if stopped.
        """
        tip        = self.chain.tip
        height     = self.height_next = tip.header.height + 1
        epoch      = get_epoch(height)
        prev_hash  = tip.block_hash
        reward     = block_reward(height)
        difficulty = self.chain.difficulty.current
        target     = "0" * difficulty

        coinbase = Transaction.coinbase(self.miner_id, reward, height)
        txs = [coinbase] + (pending_txs or [])

        # Build DAG once per mining session
        dag_seed_bytes = self._build_dag_seed(prev_hash, height)
        dag_seed_hex   = dag_seed_bytes.hex()
        if self.verbose:
            print(f"[Miner] Building DAG for epoch {epoch} "
                  f"({get_dag_size_mb(epoch) if not self.chain.testnet else 4} MB)…")
        dag = MemoryDAG(dag_seed_bytes, epoch, testnet=self.chain.testnet)
        if self.verbose:
            print(f"[Miner] DAG ready. Mining block #{height} "
                  f"(diff={difficulty}, target={target}…)")

        nonce     = 0
        t_start   = time.time()
        attempts  = 0

        while not self._stop.is_set():
            nonce += 1
            attempts += 1

            # ── random memory walk ────────────────
            seed_hash = hashlib.sha3_256(
                f"{prev_hash}:{self.miner_id}:{nonce}".encode()
            ).digest()
            walk_hash, latency_ns = random_memory_walk(
                dag, seed_hash,
                steps=min(MEMORY_WALK_STEPS, 500) if self.chain.testnet else MEMORY_WALK_STEPS
            )

            # ── validate latency ──────────────────
            if not latency_is_valid(latency_ns, self.ram_type):
                continue  # reject this attempt

            # ── compute score ─────────────────────
            score = compute_score(attempts, self.ram_type, self.threads)

            # ── build candidate header ────────────
            header = BlockHeader(
                height=height,
                prev_hash=prev_hash,
                timestamp=int(time.time()),
                nonce=nonce,
                miner_id=self.miner_id,
                ram_type=self.ram_type.value,
                thread_count=self.threads,
                epoch=epoch,
                difficulty=difficulty,
                dag_seed=dag_seed_hex,
                latency_proof=round(latency_ns, 4),
                memory_proof=walk_hash.hex(),
                score=round(score, 6),
            )

            candidate = Block(header=header, transactions=txs)
            candidate.block_hash = candidate.compute_hash()

            if candidate.block_hash.startswith(target):
                elapsed = time.time() - t_start
                if self.verbose:
                    print(f"\n[Miner] ✓ Block #{height} found!")
                    print(f"        Hash     : {candidate.block_hash[:24]}…")
                    print(f"        Nonce    : {nonce:,}")
                    print(f"        Time     : {elapsed:.2f}s")
                    print(f"        Latency  : {latency_ns:.1f}ns avg")
                    print(f"        Score    : {score:.2f}")
                    print(f"        Reward   : {reward} {COIN_SYMBOL}")
                return candidate

        return None  # stopped

    def start_continuous(self):
        """Mine continuously until stop() is called."""
        self._stop.clear()
        while not self._stop.is_set():
            blk = self.mine_block()
            if blk:
                ok, reason = self.chain.add_block(blk)
                if ok:
                    print(f"[Miner] Block #{blk.header.height} accepted ✓")
                else:
                    print(f"[Miner] Block rejected: {reason}")

    def stop(self):
        self._stop.set()

# ─────────────────────────────────────────────
# CHAIN VALIDATOR (full replay)
# ─────────────────────────────────────────────
def validate_full_chain(chain: PoLMChain) -> Tuple[bool, List[str]]:
    errors = []
    for i, blk in enumerate(chain.chain[1:], start=1):
        prev = chain.chain[i-1]
        if blk.header.prev_hash != prev.block_hash:
            errors.append(f"Block {i}: prev_hash broken")
        if blk.compute_hash() != blk.block_hash:
            errors.append(f"Block {i}: hash mismatch")
        if blk.header.height != i:
            errors.append(f"Block {i}: height mismatch")
    return len(errors) == 0, errors

# ─────────────────────────────────────────────
# QUICK TEST
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print(f"  PoLM-X v{POLM_VERSION} — Memory-Hard + Latency-Hard PoW")
    print("=" * 60)

    chain  = PoLMChain(chain_file="/tmp/polmx_test.json", testnet=True)
    miner  = PoLMXMiner(chain, miner_id="TestMiner_v2", ram_type=RAMType.DDR3)

    print("\n[Chain] Mining 3 test blocks…\n")
    for _ in range(3):
        blk = miner.mine_block()
        if blk:
            ok, reason = chain.add_block(blk)
            print(f"  add_block: {ok} — {reason}")

    valid, errs = validate_full_chain(chain)
    print(f"\n[Chain] Full validation: {'✓ VALID' if valid else '✗ INVALID'}")
    if errs:
        for e in errs:
            print(f"  ERROR: {e}")

    print("\n[Chain] Summary:")
    for k, v in chain.summary().items():
        print(f"  {k:20s}: {v}")
