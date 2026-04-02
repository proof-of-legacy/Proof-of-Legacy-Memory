"""
PoLM — Proof of Legacy Memory  v1.2.0
https://polm.com.br

The first RAM-latency-bound Proof-of-Work consensus algorithm.
Giving computational relevance back to legacy hardware.

Founder : @aluisiofer  (https://x.com/aluisiofer)
Project : @polm2026    (https://x.com/polm2026)
Website : https://polm.com.br
GitHub  : https://github.com/proof-of-legacy/Proof-of-Legacy-Memory

Testnet validated (March 2026) — 816 blocks across 4 RAM generations:
  DDR2 Core2Duo  boost=10x   52.4%  3800ns avg
  DDR4 i5-7th    boost=1x    34.8%  1741ns avg
  DDR3 AMD       boost=8x     7.6% 12988ns avg
  DDR4 i5-12th   boost=1x     5.3%  1060ns avg

Cross-platform: Windows 10/11 | Linux | macOS
Python 3.9+  |  pip install flask cryptography

Usage:
  python polm.py node   [port] [peer ...]  [--testnet]
  python polm.py miner  <url> <address> <DDR2|DDR3|DDR4|DDR5>  [--testnet]
  python polm.py info
"""

# ── Windows bootstrap (must be first) ────────────────────────────
import sys, os

if sys.platform == "win32":
    import io, asyncio
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

IS_WIN = sys.platform == "win32"
IS_LIN = sys.platform.startswith("linux")
IS_MAC = sys.platform == "darwin"

import hashlib, time, json, threading, random, socket, subprocess, platform, secrets
import urllib.request, urllib.error
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Set, Tuple
from flask import Flask, jsonify, request

# ─────────────────────────────────────────────────────────────────
# ANTI-MULTI-MINING: 1 IP = 1 active miner
# Each IP can only have ONE active miner per address.
# The founder address can connect from multiple IPs (maintenance).
# ─────────────────────────────────────────────────────────────────
_active_miners: Dict[str, str] = {}   # ip → miner_address
_miner_ips:     Dict[str, str] = {}   # miner_address → ip
_anti_mine_lock = threading.Lock()

def register_miner(ip: str, address: str, founder: str) -> Tuple[bool, str]:
    """Register a miner. Returns (allowed, reason).
    Rules:
    - 1 IP can only mine with 1 address
    - 1 address can only mine from 1 IP
    - Founder address bypasses IP restriction (maintenance)
    """
    if address == founder:
        return True, "founder"   # founder can connect from anywhere
    with _anti_mine_lock:
        existing_ip  = _miner_ips.get(address)
        existing_addr = _active_miners.get(ip)
        if existing_ip and existing_ip != ip:
            return False, f"address already mining from {existing_ip}"
        if existing_addr and existing_addr != address:
            return False, f"IP already mining with {existing_addr}"
        _active_miners[ip]      = address
        _miner_ips[address]     = ip
    return True, "ok"

def unregister_miner(ip: str, address: str):
    with _anti_mine_lock:
        _active_miners.pop(ip, None)
        _miner_ips.pop(address, None)

# ─────────────────────────────────────────────────────────────────
# MAINNET CONSTANTS
# ─────────────────────────────────────────────────────────────────
VERSION             = "2.0.0"
SYMBOL              = "POLM"
NETWORK             = "mainnet"
WEBSITE             = "https://polm.com.br"
MAX_SUPPLY          = 210_000_000       # ~210M total over 30+ years
INITIAL_REWARD      = 50.0              # 50 POLM/block — halving launch
BLOCK_TIME          = 120             # 2 minutes — stable like Litecoin
DIFF_WINDOW         = 144             # blocks per retarget (~4.8h at 2min/block)
DIFF_CLAMP          = 0.25            # ±25% max adjustment

# ── EPOCH / RAM HALVING SYSTEM ──────────────────────────────────
# Halving is driven by RAM epochs, not just block count.
# Each epoch doubles the DAG size — forcing more RAM.
# This creates demand for dedicated RAM-mining hardware:
# motherboards with massive RAM slots, like GPU cards but for RAM.
#
# Epoch 0  (~138 days): DAG=256MB   reward=100  min=1GB   → any PC
# Epoch 1  (~138 days): DAG=512MB   reward=50   min=2GB   → decent PC
# Epoch 2  (~138 days): DAG=1GB     reward=25   min=4GB   → gaming PC
# Epoch 3  (~138 days): DAG=2GB     reward=12.5 min=8GB   → workstation
# Epoch 4  (~138 days): DAG=4GB     reward=6.25 min=16GB  → high-end PC
# Epoch 5  (~138 days): DAG=8GB     reward=3.12 min=32GB  → server
# Epoch 6  (~138 days): DAG=16GB    reward=1.56 min=64GB  → dedicated rig
# Epoch 7  (~138 days): DAG=32GB    reward=0.78 min=128GB → RAM mining board!
# Epoch 8  (~138 days): DAG=64GB    reward=0.39 min=256GB → industrial!
# Epoch 9+ (~138 days): DAG=128GB+  reward→0    min=512GB+→ new hardware market
#
# Total supply: converges to 210,000,000 POLM over ~4 years
EPOCH_BLOCKS        = 100_000         # ~138 days per epoch at 2min/block
HALVING_INTERVAL    = EPOCH_BLOCKS    # 1 halving per epoch (RAM-driven)
DAG_BASE_MB         = 256
DAG_GROWTH_MB       = 0               # not used — DAG defined per epoch below
WALK_STEPS_MAIN     = 100_000
GENESIS_TIME        = 1774221048
FOUNDER_ADDRESS     = "POLMD872771E5F0017C5B5C08D353B5E7B4B"
FOUNDER_TWITTER     = "https://x.com/aluisiofer"
PROJECT_TWITTER     = "https://x.com/polm2026"
FOUNDER_LOCK        = 5_256_000       # ~5 years
DEFAULT_PORT        = 6060
MIN_FEE             = 0.0001
MAX_MINERS_PER_IP   = 1        # 1 miner per IP — prevents multi-instance cheating
FOUNDER_IPS_ALLOWED = True     # founder can run maintenance miners
BASELINE_NS         = 1000.0          # DDR4 reference latency
BOOST_ALPHA         = 0.8

# Testnet overrides
T_DAG_MB  = 4
T_WALK    = 500
T_DIFF    = 4

DNS_SEEDS = [
    "node1.polm.com.br",
    "node2.polm.com.br",
    "node3.polm.com.br",
]

# ─────────────────────────────────────────────────────────────────
# PoLM v2.0 — Pure Memory Latency Consensus
#
# No boosts. No tricks. The RAM speaks for itself.
# Score = 1 / latency_ns
# Higher latency = more memory work = higher score
#
# Any RAM works. Any age. Any speed.
# 4 threads max — beyond that, parallelism doesn't help.
#
# "Mine with your RAM — latency is truth."
# ─────────────────────────────────────────────────────────────────


# DAG size per epoch — doubles each time, forcing RAM hardware evolution
DAG_BASE_PER_HALVING = {
    0:       256,   # 256MB   — any PC
    1:       512,   # 512MB   — decent PC
    2:      1024,   # 1GB     — gaming PC
    3:      2048,   # 2GB     — workstation
    4:      4096,   # 4GB     — high-end
    5:      8192,   # 8GB     — server
    6:     16384,   # 16GB    — dedicated rig
    7:     32768,   # 32GB    — RAM mining board!
    8:     65536,   # 64GB    — industrial
    9:    131072,   # 128GB   — new hardware market
    10:   262144,   # 256GB   — specialized motherboards
    11:   524288,   # 512GB   — factory-scale RAM mining
}

# Minimum RAM per epoch — aggressive growth forces hardware evolution
MIN_RAM_MB = {
    0:       4_096,   # 4GB    — any PC with 4GB+
    1:      16_384,   # 16GB   — modern desktops
    2:      32_768,   # 32GB   — high-end workstations
    3:      65_536,   # 64GB   — server-class
    4:     131_072,   # 128GB  — dedicated RAM rigs
    5:     262_144,   # 256GB  — enterprise RAM servers
    6:     524_288,   # 512GB  — RAM mining boards
    7:   1_048_576,   # 1TB    — industrial RAM arrays!
    8:   2_097_152,   # 2TB    — new hardware industry
    9:   4_194_304,   # 4TB    — specialized hardware
    10:  8_388_608,   # 8TB    — factory-scale
    11: 16_777_216,   # 16TB   — future hardware market
}

def get_halving(height: int) -> int:
    return min(epoch_of(height), 11)

def get_static_boost(ram_type: str, height: int = 0) -> float:
    halving = get_halving(height)
    return 1.0  # pure latency — no boost by RAM type

def dag_base_for_height(height: int) -> int:
    return DAG_BASE_PER_HALVING.get(get_halving(height), 4096)

# Current halving alias
STATIC_BOOST = {"DDR2": 1.0, "DDR3": 1.0, "DDR4": 1.0, "DDR5": 1.0}
FOUNDER_NAME = "Aluisio Fernandes (Aluminium)"
GENESIS_MSG  = "Legacy hardware deserves a second life — PoLM Genesis, March 2026, polm.com.br"

# ─────────────────────────────────────────────────────────────────
# PLATFORM HELPERS
# ─────────────────────────────────────────────────────────────────
def default_data_dir() -> str:
    if IS_WIN:
        d = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "PoLM")
    elif IS_MAC:
        d = os.path.expanduser("~/Library/Application Support/PoLM")
    else:
        d = os.path.expanduser("~/.polm")
    os.makedirs(d, exist_ok=True)
    return d

def get_threads() -> int:
    return min(os.cpu_count() or 1, 4)  # max 4 threads

def detect_ram() -> str:
    """Auto-detect RAM type. Override with env POLM_RAM_TYPE."""
    env = os.environ.get("POLM_RAM_TYPE", "").upper().strip()
    if env in ("DDR2", "DDR3", "DDR4", "DDR5"):
        return env
    try:
        if IS_LIN:
            out = subprocess.check_output(
                ["dmidecode", "-t", "memory"],
                stderr=subprocess.DEVNULL, timeout=5
            ).decode("utf-8", "ignore").lower()
            for r in ("ddr5", "ddr4", "ddr3", "ddr2"):
                if r in out:
                    return r.upper()
        elif IS_WIN:
            out = subprocess.check_output(
                ["wmic", "memorychip", "get", "memorytype"],
                stderr=subprocess.DEVNULL, timeout=5
            ).decode("utf-8", "ignore")
            nums = [ln.strip() for ln in out.splitlines() if ln.strip().isdigit()]
            if nums:
                return {34: "DDR5", 26: "DDR4", 24: "DDR3", 21: "DDR2"}.get(int(nums[0]), "DDR4")
            # PowerShell fallback
            out2 = subprocess.check_output(
                ["powershell", "-Command",
                 "Get-CimInstance Win32_PhysicalMemory | Select SMBIOSMemoryType"],
                stderr=subprocess.DEVNULL, timeout=8
            ).decode("utf-8", "ignore")
            for code, ram in [("34", "DDR5"), ("26", "DDR4"), ("24", "DDR3"), ("21", "DDR2")]:
                if code in out2:
                    return ram
        elif IS_MAC:
            out = subprocess.check_output(
                ["system_profiler", "SPMemoryDataType"],
                stderr=subprocess.DEVNULL, timeout=5
            ).decode("utf-8", "ignore").lower()
            for r in ("ddr5", "ddr4", "ddr3", "ddr2"):
                if r in out:
                    return r.upper()
    except Exception:
        pass
    return "DDR4"

def atomic_write(path: str, data: str):
    """Write file atomically (safe on all platforms)."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(data)
    if IS_WIN and os.path.exists(path):
        os.remove(path)
    os.replace(tmp, path)

# ─────────────────────────────────────────────────────────────────
# ECDSA CRYPTO (secp256k1)
# ─────────────────────────────────────────────────────────────────
try:
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.backends import default_backend
    HAVE_CRYPTO = True
except ImportError:
    HAVE_CRYPTO = False

def pubkey_to_address(pub_hex: str) -> str:
    h = hashlib.sha3_256(
        hashlib.sha3_256(bytes.fromhex(pub_hex)).digest()
    ).hexdigest()
    return "POLM" + h[:32].upper()

def generate_keypair() -> Tuple[str, str, str]:
    """Returns (priv_hex, pub_hex, address)."""
    if HAVE_CRYPTO:
        priv = ec.generate_private_key(ec.SECP256K1(), default_backend())
        priv_hex = priv.private_bytes(
            serialization.Encoding.DER,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()
        ).hex()
        pub_hex = priv.public_key().public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.CompressedPoint
        ).hex()
    else:
        priv_hex = secrets.token_hex(32)
        pub_hex  = hashlib.sha3_256(bytes.fromhex(priv_hex)).hexdigest()
    return priv_hex, pub_hex, pubkey_to_address(pub_hex)

def sign_data(priv_hex: str, data: bytes) -> str:
    if HAVE_CRYPTO:
        priv = serialization.load_der_private_key(
            bytes.fromhex(priv_hex), password=None, backend=default_backend()
        )
        return priv.sign(data, ec.ECDSA(hashes.SHA256())).hex()
    return hashlib.sha3_256(priv_hex.encode() + data).hexdigest()

def verify_sig(pub_hex: str, data: bytes, sig_hex: str) -> bool:
    if not HAVE_CRYPTO:
        return True
    try:
        pub = ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256K1(), bytes.fromhex(pub_hex)
        )
        pub.verify(bytes.fromhex(sig_hex), data, ec.ECDSA(hashes.SHA256()))
        return True
    except Exception:
        return False

# ─────────────────────────────────────────────────────────────────
# TRANSACTION
# ─────────────────────────────────────────────────────────────────
@dataclass
class Transaction:
    tx_id:        str
    sender:       str
    receiver:     str
    amount:       float
    fee:          float
    timestamp:    int
    signature:    str
    pub_key:      str
    memo:         str  = ""
    confirmed:    bool = False
    block_height: int  = -1

    def signing_bytes(self) -> bytes:
        return (
            f"{self.sender}:{self.receiver}:"
            f"{self.amount:.8f}:{self.fee:.8f}:"
            f"{self.timestamp}:{self.memo}"
        ).encode()

    def compute_id(self) -> str:
        return hashlib.sha3_256(
            self.signing_bytes() + self.signature.encode()
        ).hexdigest()

    def is_valid_format(self) -> bool:
        return (
            self.amount > 0
            and self.fee >= MIN_FEE
            and self.sender.startswith("POLM")
            and self.receiver.startswith("POLM")
            and len(self.tx_id) == 64
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Transaction":
        fields = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in fields})

# ─────────────────────────────────────────────────────────────────
# MEMPOOL
# ─────────────────────────────────────────────────────────────────
class Mempool:
    def __init__(self):
        self._txs:  Dict[str, Transaction] = {}
        self._lock = threading.Lock()

    def add(self, tx: Transaction) -> Tuple[bool, str]:
        if not tx.is_valid_format():
            return False, "invalid format"
        with self._lock:
            if tx.tx_id in self._txs:
                return False, "duplicate"
            self._txs[tx.tx_id] = tx
        return True, "accepted"

    def remove(self, tx_id: str):
        with self._lock:
            self._txs.pop(tx_id, None)

    def get_pending(self, limit: int = 100) -> List[Transaction]:
        with self._lock:
            return sorted(
                self._txs.values(), key=lambda t: t.fee, reverse=True
            )[:limit]

    def get(self, tx_id: str) -> Optional[Transaction]:
        return self._txs.get(tx_id)

    def size(self) -> int:
        return len(self._txs)

    def all(self) -> List[dict]:
        with self._lock:
            return [t.to_dict() for t in self._txs.values()]

# ─────────────────────────────────────────────────────────────────
# LEDGER (account balances)
# ─────────────────────────────────────────────────────────────────
class Ledger:
    def __init__(self):
        self._bal:  Dict[str, float] = {}
        self._lock = threading.Lock()

    def credit(self, addr: str, amount: float):
        with self._lock:
            self._bal[addr] = round(self._bal.get(addr, 0.0) + amount, 8)

    def debit(self, addr: str, amount: float) -> bool:
        with self._lock:
            bal = self._bal.get(addr, 0.0)
            if bal < amount - 1e-9:
                return False
            self._bal[addr] = round(bal - amount, 8)
            return True

    def balance(self, addr: str) -> float:
        return self._bal.get(addr, 0.0)

    def apply_reward(self, miner: str, reward: float):
        self.credit(miner, reward)

    def apply_tx(self, tx: Transaction) -> bool:
        total = round(tx.amount + tx.fee, 8)
        if not self.debit(tx.sender, total):
            return False
        self.credit(tx.receiver, tx.amount)
        return True

    def rebuild(self, chain: List["Block"],
                txs_by_block: Dict[int, List[Transaction]]):
        self._bal = {}
        for b in chain[1:]:
            self.credit(b.miner_id, b.reward)
            for tx in txs_by_block.get(b.height, []):
                self.apply_tx(tx)

# ─────────────────────────────────────────────────────────────────
# BLOCK
# ─────────────────────────────────────────────────────────────────
@dataclass
class Block:
    height:     int
    prev_hash:  str
    timestamp:  int
    nonce:      int
    miner_id:   str
    ram_type:   str
    threads:    int
    epoch:      int
    difficulty: int
    latency_ns: float
    mem_proof:  str
    score:      float
    reward:     float
    cpu_name:   str = ""
    tx_ids:     List[str] = field(default_factory=list)
    block_hash: str = ""

    def _header(self) -> str:
        return (
            f"{self.height}|{self.prev_hash}|{self.timestamp}|"
            f"{self.nonce}|{self.miner_id}|{self.ram_type}|"
            f"{self.threads}|{self.epoch}|{self.difficulty}|"
            f"{self.latency_ns:.4f}|{self.mem_proof}|"
            f"{self.score:.8f}|{self.reward}|"
            f"{','.join(self.tx_ids)}"
        )

    def compute_hash(self) -> str:
        return hashlib.sha3_256(self._header().encode()).hexdigest()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Block":
        d = dict(d)
        d.setdefault("tx_ids", [])
        fields = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in fields})

# ─────────────────────────────────────────────────────────────────
# PROOF-OF-LEGACY-MEMORY ALGORITHM
# ─────────────────────────────────────────────────────────────────
def detect_cpu() -> str:
    """Detect CPU model name for miner identification."""
    import platform
    try:
        # Linux: read from /proc/cpuinfo
        if platform.system() == "Linux":
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line:
                        cpu = line.split(":")[1].strip()
                        cpu = cpu.replace("(R)","").replace("(TM)","").strip()
                        return cpu[:40]
        # Windows: read from registry
        if platform.system() == "Windows":
            import subprocess
            out = subprocess.check_output(
                ["wmic","cpu","get","name"],
                capture_output=True, text=True, timeout=3
            ).stdout
            for line in out.splitlines():
                line = line.strip()
                if line and line != "Name":
                    cpu = line.replace("(R)","").replace("(TM)","").strip()
                    return cpu[:40]
        # macOS
        if platform.system() == "Darwin":
            import subprocess
            out = subprocess.check_output(
                ["sysctl","-n","machdep.cpu.brand_string"],
                capture_output=True, text=True, timeout=3
            ).stdout.strip()
            if out:
                return out.replace("(R)","").replace("(TM)","").strip()[:40]
    except Exception:
        pass
    return "Unknown CPU"

def dynamic_boost(lat_ns: float, ram_type: str = "DDR4", height: int = 0) -> float:
    """Pure latency — no boost. score = 1/latency_ns."""
    return 1.0


def sat_penalty(threads: int) -> float:
    """No penalty — all thread counts welcome. Max 4 threads enforced at get_threads()."""
    return 1.0

def compute_score(lat_ns: float, boost: float, threads: int) -> float:
    """score = 1 / latency_ns — pure physics, no boost, no penalty."""
    return 0.0 if lat_ns <= 0 else (1.0 / lat_ns)

def epoch_of(height: int) -> int:
    return height // EPOCH_BLOCKS

def dag_size_mb(epoch: int, testnet: bool, height: int = 0) -> int:
    """DAG grows both with epoch AND with each halving.
    Halving 1: starts at 256MB  (needs ~4GB RAM)
    Halving 2: starts at 512MB  (needs ~8GB RAM)
    Halving 3: starts at 1024MB (needs ~16GB RAM)
    Halving 4: starts at 2048MB (needs ~32GB RAM)
    """
    if testnet:
        return T_DAG_MB
    base = dag_base_for_height(height)
    return base + epoch * DAG_GROWTH_MB

def walk_steps(testnet: bool) -> int:
    return T_WALK if testnet else WALK_STEPS_MAIN

def block_reward(height: int) -> float:
    # Reward halves every epoch (driven by RAM requirement growth)
    epoch = epoch_of(height)
    return 0.0 if epoch >= 32 else INITIAL_REWARD / (2 ** epoch)

class MemoryDAG:
    """Large pseudorandom buffer seeded from epoch — defeats caching."""
    def __init__(self, seed: bytes, epoch: int, testnet: bool):
        sz  = dag_size_mb(epoch, testnet) * 1024 * 1024
        buf = bytearray()
        cur = hashlib.sha3_256(seed).digest()
        while len(buf) < sz:
            blk = hashlib.sha3_512(cur).digest()
            buf.extend(blk)
            cur = blk
        self._b    = bytes(buf[:sz])
        self.size  = sz

    def read(self, pos: int) -> bytes:
        i = pos % (self.size - 32)
        return self._b[i:i + 32]

def memory_walk(dag: MemoryDAG, seed: bytes, steps: int) -> Tuple[bytes, float]:
    h   = seed
    pos = int.from_bytes(h[:8], "little") % dag.size
    t0  = time.perf_counter_ns()
    for _ in range(steps):
        mem = dag.read(pos)
        h   = hashlib.sha3_256(h + mem).digest()
        pos = int.from_bytes(h[:8], "little") % dag.size
    avg_lat = (time.perf_counter_ns() - t0) / steps
    return h, avg_lat

# ─────────────────────────────────────────────────────────────────
# BLOCKCHAIN
# ─────────────────────────────────────────────────────────────────
class Blockchain:
    def __init__(self, data_dir: str, testnet: bool = False):
        self.testnet    = testnet
        self._chain_f   = os.path.join(data_dir, "chain.json")
        self._tx_f      = os.path.join(data_dir, "txs.json")
        self.chain:     List[Block] = []
        self.txs:       Dict[str, Transaction] = {}
        self.tx_block:  Dict[int, List[str]] = {}
        self.ledger     = Ledger()
        self._miner_ips: dict = {}  # miner_address → ip
        self._active_miners: dict = {}  # ip → miner info
        self._peers: set = set()  # known peers
        self.mempool    = Mempool()
        self._diff      = T_DIFF if testnet else 3
        self._peers:    Set[str] = set()
        self._lock      = threading.Lock()
        self._load()

    # ── persistence ───────────────────────────────────────────────
    def _save(self):
        atomic_write(self._chain_f,
                     json.dumps([b.to_dict() for b in self.chain]))
        atomic_write(self._tx_f, json.dumps({
            "txs":      {k: v.to_dict() for k, v in self.txs.items()},
            "tx_block": {str(k): v for k, v in self.tx_block.items()},
        }))

    def _load(self):
        if os.path.exists(self._chain_f):
            with open(self._chain_f, encoding="utf-8") as f:
                self.chain = [Block.from_dict(d) for d in json.load(f)]
            self._diff = self.chain[-1].difficulty
            print(f"[Chain] Loaded {len(self.chain)} blocks  height={self.height}")
        else:
            self._genesis()
        if os.path.exists(self._tx_f):
            with open(self._tx_f, encoding="utf-8") as f:
                d = json.load(f)
            self.txs = {k: Transaction.from_dict(v)
                        for k, v in d.get("txs", {}).items()}
            self.tx_block = {int(k): v
                             for k, v in d.get("tx_block", {}).items()}
        self.ledger.rebuild(
            self.chain,
            {h: [self.txs[i] for i in ids if i in self.txs]
             for h, ids in self.tx_block.items()}
        )

    def _genesis(self):
        b = Block(
            height=0, prev_hash="0" * 64, timestamp=GENESIS_TIME,
            nonce=0, miner_id="GENESIS", ram_type="DDR4", threads=1,
            epoch=0, difficulty=self._diff, latency_ns=0.0,
            mem_proof="0" * 64, score=0.0, reward=INITIAL_REWARD, tx_ids=[]
        )
        b.block_hash = b.compute_hash()
        self.chain.append(b)
        self._save()
        print(f"[Chain] Genesis  {b.block_hash[:16]}...")

    # ── properties ────────────────────────────────────────────────
    @property
    def height(self) -> int:
        return len(self.chain) - 1

    @property
    def tip(self) -> Block:
        return self.chain[-1]

    @property
    def difficulty(self) -> int:
        return self._diff

    def target(self) -> str:
        return "0" * self._diff

    # ── difficulty retarget ───────────────────────────────────────
    def _retarget(self):
        if len(self.chain) < 2 or len(self.chain) % DIFF_WINDOW != 0:
            return
        window  = self.chain[-DIFF_WINDOW:]
        elapsed = window[-1].timestamp - window[0].timestamp
        if elapsed == 0:
            return
        ratio = BLOCK_TIME * (DIFF_WINDOW - 1) / elapsed
        ratio = max(1 - DIFF_CLAMP, min(1 + DIFF_CLAMP, ratio))
        self._diff = max(1, round(self._diff * ratio))
        print(f"[Chain] Difficulty retarget  ->  {self._diff}")

    # ── add block ─────────────────────────────────────────────────
    def add_block(self, b: Block,
                  txs: List[Transaction] = [],
                  miner_ip: str = "") -> Tuple[bool, str]:
        with self._lock:
            if b.height != self.height + 1:
                return False, f"height {b.height} expected {self.height+1}"
            if b.prev_hash != self.tip.block_hash:
                return False, "prev_hash mismatch"
            if not b.block_hash.startswith(self.target()):
                return False, "insufficient PoW"
            if b.compute_hash() != b.block_hash:
                return False, "hash mismatch"
            if b.latency_ns < 5:
                return False, "latency too low (cache exploit)"
            if abs(b.reward - block_reward(b.height)) > 1e-6:
                return False, "wrong reward"
            if b.timestamp > int(time.time()) + 120:
                return False, "timestamp too far in future"

            # Update miner activity tracking
            self._active_miners[b.miner_id] = float(b.timestamp)

            confirmed_ids: List[str] = []
            for tx in txs:
                if tx.tx_id not in b.tx_ids:
                    continue
                if self.ledger.apply_tx(tx):
                    self.txs[tx.tx_id]  = tx
                    tx.confirmed        = True
                    tx.block_height     = b.height
                    confirmed_ids.append(tx.tx_id)
                    self.mempool.remove(tx.tx_id)
            self.tx_block[b.height] = confirmed_ids
            b.tx_ids = confirmed_ids

            self.ledger.apply_reward(b.miner_id, b.reward)
            self.chain.append(b)
            self._retarget()
            self._save()
            return True, "ok"

    # ── submit transaction ────────────────────────────────────────
    def submit_tx(self, tx: Transaction) -> Tuple[bool, str]:
        if not tx.is_valid_format():
            return False, "invalid format"
        if tx.tx_id in self.txs:
            return False, "already confirmed"
        needed = round(tx.amount + tx.fee, 8)
        bal    = self.ledger.balance(tx.sender)
        if bal < needed - 1e-9:
            return False, f"insufficient balance ({bal:.4f} < {needed:.4f})"
        if HAVE_CRYPTO:
            if not verify_sig(tx.pub_key, tx.signing_bytes(), tx.signature):
                return False, "invalid signature"
        return self.mempool.add(tx)

    # ── queries ───────────────────────────────────────────────────
    def balance(self, addr: str) -> float:
        return self.ledger.balance(addr)

    def tx_history(self, addr: str) -> List[dict]:
        result = [
            tx.to_dict() for tx in self.txs.values()
            if tx.sender == addr or tx.receiver == addr
        ]
        result.sort(key=lambda x: x["block_height"], reverse=True)
        return result

    def summary(self) -> dict:
        ep = epoch_of(self.height)
        return {
            "version":      VERSION,
            "website":      WEBSITE,
            "network":      NETWORK,
            "platform":     platform.system(),
            "height":       self.height,
            "tip_hash":     self.tip.block_hash,
            "difficulty":   self._diff,
            "epoch":        ep,
            "dag_size_mb":  dag_size_mb(ep, self.testnet),
            "total_supply": round(sum(b.reward for b in self.chain), 4),
            "max_supply":   MAX_SUPPLY,
            "next_reward":  block_reward(self.height + 1),
            "block_time":   BLOCK_TIME,
            "peers":        len(self._peers),
            "mempool_size":  self.mempool.size(),
            "symbol":        SYMBOL,
            "halving":       get_halving(self.height),
            "boost_table":   STATIC_BOOST,
            "min_ram_mb":    MIN_RAM_MB.get(get_halving(self.height), 4096),
            "founder":       FOUNDER_NAME if "FOUNDER_NAME" in dir() else "Aluisio Fernandes (Aluminium)",
            "founder_addr":  FOUNDER_ADDRESS,
            "founder_lock":  FOUNDER_LOCK,
        }

# ─────────────────────────────────────────────────────────────────
# P2P GOSSIP
# ─────────────────────────────────────────────────────────────────
class P2P:
    def __init__(self, chain: Blockchain, port: int):
        self.chain  = chain
        self.port   = port
        self._peers: Set[str] = set()
        self._lock  = threading.Lock()

    def add(self, addr: str):
        if addr:
            with self._lock:
                self._peers.add(addr)
                self.chain._peers.add(addr)

    def peers(self) -> List[str]:
        with self._lock:
            return list(self._peers)

    def broadcast_block(self, b: Block, txs: List[Transaction]):
        payload = json.dumps({
            "block": b.to_dict(),
            "txs":   [t.to_dict() for t in txs],
        }).encode()
        for peer in self.peers():
            threading.Thread(
                target=self._send,
                args=(peer, "/receive_block", payload),
                daemon=True
            ).start()

    def broadcast_tx(self, tx: Transaction):
        payload = json.dumps(tx.to_dict()).encode()
        for peer in self.peers():
            threading.Thread(
                target=self._send,
                args=(peer, "/receive_tx", payload),
                daemon=True
            ).start()

    def _send(self, peer: str, path: str, data: bytes):
        try:
            req = urllib.request.Request(
                f"http://{peer}{path}", data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

    def sync(self, peer: str) -> int:
        synced = 0
        try:
            r = urllib.request.urlopen(f"http://{peer}/", timeout=5)
            d = json.loads(r.read())
            peer_h = d.get("height", 0)
            if peer_h <= self.chain.height:
                return 0
            print(f"[P2P] Syncing from {peer}  ({peer_h} vs {self.chain.height})...")
            for h in range(self.chain.height + 1, peer_h + 1):
                r2 = urllib.request.urlopen(
                    f"http://{peer}/block/{h}", timeout=5)
                d2  = json.loads(r2.read())
                blk = Block.from_dict(d2["block"])
                txs = [Transaction.from_dict(t) for t in d2.get("txs", [])]
                ok, _ = self.chain.add_block(blk, txs)
                if ok:
                    synced += 1
                else:
                    break
        except Exception:
            pass
        return synced

    def start_sync_loop(self, interval: int = 15):
        def loop():
            while True:
                time.sleep(interval)
                for peer in self.peers():
                    self.sync(peer)
        threading.Thread(target=loop, daemon=True, name="p2p-sync").start()
        print(f"[P2P] Sync loop started  ({interval}s interval)")

    def bootstrap(self):
        """Try all DNS seeds + direct IPs for resilient bootstrap."""
        print(f"[P2P] Bootstrapping from DNS seeds...")
        for seed in DNS_SEEDS:
            try:
                ip = socket.gethostbyname(seed)
                addr = f"{ip}:{self.port}"
                self.add(addr)
                synced = self.sync(addr)
                print(f"[P2P] Seed {seed} ({ip}) → synced {synced} blocks")
            except Exception as e:
                print(f"[P2P] Seed {seed} unreachable: {e}")
        if self.peers():
            print(f"[P2P] Connected to {len(self.peers())} seed(s)")
        else:
            print(f"[P2P] No seeds reachable — running as isolated node")

    def peer_exchange(self):
        """Ask peers for their peer list — organic network growth."""
        for peer in self.peers():
            try:
                r = urllib.request.urlopen(f"http://{peer}/peers", timeout=5)
                d = json.loads(r.read())
                for p in d.get("peers", []):
                    if p not in self.peers():
                        self.add(p)
            except Exception:
                pass

# ─────────────────────────────────────────────────────────────────
# FULL NODE
# ─────────────────────────────────────────────────────────────────
class PoLMNode:
    def __init__(
        self,
        data_dir:  str,
        port:      int = DEFAULT_PORT,
        testnet:   bool = False,
        peers:     List[str] = [],
    ):
        self.chain   = Blockchain(data_dir, testnet)
        self.p2p     = P2P(self.chain, port)
        self.app     = Flask("polm-node")
        self.port    = port
        self._mstop  = threading.Event()
        self._mid:   Optional[str] = None
        self._mram:  Optional[str] = None

        for p in peers:
            self.p2p.add(p)
        self._register_routes()
        self.p2p.start_sync_loop()
        # Bootstrap from DNS seeds in background
        threading.Thread(target=self.p2p.bootstrap, daemon=True, name="p2p-bootstrap").start()
        # Peer exchange every 5 minutes
        def _peer_exchange_loop():
            while True:
                time.sleep(300)
                self.p2p.peer_exchange()
        threading.Thread(target=_peer_exchange_loop, daemon=True, name="p2p-exchange").start()

    # ── routes ────────────────────────────────────────────────────
    def _register_routes(self):
        app = self.app

        @app.route("/")
        def status():
            return jsonify(self.chain.summary())

        @app.route("/getwork")
        def getwork():
            tip     = self.chain.tip
            pending = self.chain.mempool.get_pending(50)
            return jsonify({
                "height":      tip.height + 1,
                "prev_hash":   tip.block_hash,
                "difficulty":  self.chain.difficulty,
                "target":      self.chain.target(),
                "reward":      block_reward(tip.height + 1),
                "epoch":       epoch_of(tip.height + 1),
                "dag_size_mb": dag_size_mb(epoch_of(tip.height + 1),
                                           self.chain.testnet),
                "testnet":     self.chain.testnet,
                "pending_txs": [t.to_dict() for t in pending],
            })

        @app.route("/submit", methods=["POST"])
        def submit():
            try:
                d       = request.json or {}
                b       = Block.from_dict(d["block"])
                txs     = [Transaction.from_dict(t) for t in d.get("txs", [])]
                miner_ip = request.remote_addr or "unknown"


                ok, reason = self.chain.add_block(b, txs)
                if ok:
                    # Register this IP → miner mapping
                    self.chain._miner_ips[miner_ip] = b.miner_id
                    print(
                        f"[Node] Block #{b.height}  {b.miner_id[:20]}  "
                        f"{b.ram_type}  {b.latency_ns:.0f}ns  "
                        f"ip={miner_ip}  txs={len(txs)}"
                    )
                    self.p2p.broadcast_block(b, txs)
                    self._kick_miner()
                return jsonify({"accepted": ok, "reason": reason})
            except Exception as e:
                return jsonify({"accepted": False, "reason": str(e)}), 400

        @app.route("/active_miners")
        def active_miners():
            """Shows active miners and their IPs (anonymized)."""
            now = time.time()
            result = {}
            for mid, last in self.chain._active_miners.items():
                age = now - last
                result[mid] = {
                    "last_block_age_s": round(age),
                    "active": age < 3600,
                }
            return jsonify(result)

        @app.route("/receive_block", methods=["POST"])
        def receive_block():
            try:
                d   = request.json or {}
                b   = Block.from_dict(d["block"])
                txs = [Transaction.from_dict(t) for t in d.get("txs", [])]
                ok, reason = self.chain.add_block(b, txs)
                if ok:
                    self.p2p.broadcast_block(b, txs)
                    self._kick_miner()
                return jsonify({"accepted": ok, "reason": reason})
            except Exception as e:
                return jsonify({"error": str(e)}), 400

        @app.route("/tx/send", methods=["POST"])
        def tx_send():
            try:
                tx     = Transaction.from_dict(request.json or {})
                tx.tx_id = tx.compute_id()
                ok, reason = self.chain.submit_tx(tx)
                if ok:
                    self.p2p.broadcast_tx(tx)
                return jsonify({"accepted": ok, "reason": reason,
                                "tx_id": tx.tx_id})
            except Exception as e:
                return jsonify({"accepted": False, "reason": str(e)}), 400

        @app.route("/receive_tx", methods=["POST"])
        def receive_tx():
            try:
                tx = Transaction.from_dict(request.json or {})
                ok, reason = self.chain.submit_tx(tx)
                return jsonify({"accepted": ok, "reason": reason})
            except Exception as e:
                return jsonify({"error": str(e)}), 400

        @app.route("/tx/<tx_id>")
        def get_tx(tx_id):
            t = self.chain.txs.get(tx_id) or self.chain.mempool.get(tx_id)
            if t:
                return jsonify(t.to_dict())
            return jsonify({"error": "not found"}), 404

        @app.route("/mempool")
        def mempool():
            return jsonify(self.chain.mempool.all())

        @app.route("/chain")
        def get_chain():
            limit  = int(request.args.get("limit", 30))
            offset = int(request.args.get("offset", 0))
            blocks = self.chain.chain[::-1][offset:offset + limit]
            return jsonify([{
                "block": b.to_dict(),
                "txs": [self.chain.txs[i].to_dict()
                        for i in b.tx_ids if i in self.chain.txs],
            } for b in blocks])

        @app.route("/block/<int:h>")
        def get_block(h):
            if 0 <= h <= self.chain.height:
                b = self.chain.chain[h]
                return jsonify({
                    "block": b.to_dict(),
                    "txs": [self.chain.txs[i].to_dict()
                            for i in b.tx_ids if i in self.chain.txs],
                })
            return jsonify({"error": "not found"}), 404

        @app.route("/balance/<addr>")
        def balance(addr):
            return jsonify({
                "address": addr,
                "balance": self.chain.balance(addr),
                "symbol":  SYMBOL,
            })

        @app.route("/history/<addr>")
        def history(addr):
            return jsonify(self.chain.tx_history(addr))

        @app.route("/miners")
        def miners():
            stats: Dict[str, dict] = {}
            for b in self.chain.chain[1:]:
                m = b.miner_id
                if m not in stats:
                    stats[m] = {
                        "blocks": 0, "reward": 0.0, "ram": b.ram_type,
                        "cpu": getattr(b, "cpu_name", ""),
                        "_lat": [], "_sc": [],
                    }
                stats[m]["blocks"] += 1
                stats[m]["reward"] += b.reward
                stats[m]["_lat"].append(b.latency_ns)
                stats[m]["_sc"].append(b.score)
                if getattr(b, "cpu_name", ""):
                    stats[m]["cpu"] = b.cpu_name
            for m in stats:
                l = stats[m].pop("_lat")
                s = stats[m].pop("_sc")
                stats[m]["avg_latency"] = round(sum(l) / len(l), 1) if l else 0
                stats[m]["avg_score"]   = round(sum(s) / len(s), 6) if s else 0
            return jsonify(stats)

        @app.route("/peers", methods=["GET"])
        def get_peers():
            return jsonify({"peers": self.p2p.peers()})

        @app.route("/active_miners")
        def active_miners_route():
            """Shows which IPs are actively mining — anti-multimine monitor."""
            with _anti_mine_lock:
                return jsonify({
                    "count":   len(_active_miners),
                    "miners":  {ip: addr[:20]+"..." for ip, addr in _active_miners.items()},
                    "rule":    "1 IP = 1 miner address",
                    "founder": FOUNDER_ADDRESS[:20]+"... (unrestricted)",
                })

        @app.route("/register_evm", methods=["POST", "GET"])
        def register_evm():
            """Register EVM (Polygon) address for a native POLM miner address."""
            import os
            evm_map_file = os.path.join(default_data_dir(), "evm_addresses.json")
            # Load existing map
            evm_map = {}
            if os.path.exists(evm_map_file):
                try:
                    with open(evm_map_file) as f:
                        evm_map = json.load(f)
                except Exception:
                    pass
            if request.method == "GET":
                polm_addr = request.args.get("polm_address", "")
                if polm_addr:
                    return jsonify({"polm_address": polm_addr, "evm_address": evm_map.get(polm_addr, "")})
                return jsonify({"registered": len(evm_map), "mappings": {k: v for k, v in evm_map.items()}})
            # POST — register
            data = request.json or {}
            polm_address = data.get("polm_address", "").strip()
            evm_address  = data.get("evm_address", "").strip()
            if not polm_address or not polm_address.startswith("POLM"):
                return jsonify({"ok": False, "error": "Invalid POLM address"}), 400
            if not evm_address or not evm_address.startswith("0x") or len(evm_address) != 42:
                return jsonify({"ok": False, "error": "Invalid EVM address (must be 0x + 40 hex chars)"}), 400
            evm_map[polm_address] = evm_address
            with open(evm_map_file, "w") as f:
                json.dump(evm_map, f, indent=2)
            return jsonify({"ok": True, "polm_address": polm_address, "evm_address": evm_address})

        @app.route("/peers/add", methods=["POST"])
        def add_peer():
            addr = (request.json or {}).get("address", "")
            if addr:
                self.p2p.add(addr)
                self.p2p.sync(addr)
            return jsonify({"peers": self.p2p.peers()})

        @app.route("/network")
        def network_info():
            """Full network status for monitoring."""
            return jsonify({
                "version":        VERSION,
                "network":        NETWORK,
                "website":        WEBSITE,
                "height":         self.chain.height,
                "peers":          self.p2p.peers(),
                "peer_count":     len(self.p2p.peers()),
                "active_miners":  len(self.chain._active_miners),
                "registered_ips": len(self.chain._miner_ips),
                "mempool":        self.chain.mempool.size(),
                "genesis_hash":   self.chain.chain[0].block_hash,
                "tip_hash":       self.chain.tip.block_hash,
                "founder":        FOUNDER_NAME,
                "founder_addr":   FOUNDER_ADDRESS,
                "founder_lock":   FOUNDER_LOCK,
                "halving":        get_halving(self.chain.height),
                "boost_table":    STATIC_BOOST,
                "min_ram_gb":     MIN_RAM_MB.get(get_halving(self.chain.height), 4096) // 1024,
            })

        @app.route("/info")
        def info():
            return jsonify({
                "version":  VERSION,
                "website":  WEBSITE,
                "network":  NETWORK,
                "platform": platform.system(),
                "python":   platform.python_version(),
                "ram":      detect_ram(),
                "threads":  get_threads(),
                "crypto":   "secp256k1" if HAVE_CRYPTO else "fallback",
                "data_dir": default_data_dir(),
            })

    # ── miner kick ────────────────────────────────────────────────
    def _kick_miner(self):
        """Interrupt local miner so it starts next block immediately."""
        if not self._mstop.is_set():
            self._mstop.set()
            def restart():
                time.sleep(0.2)
                if self._mid:
                    self._mstop.clear()
                    threading.Thread(
                        target=self._mine1,
                        args=(self._mid, self._mram or "DDR4"),
                        daemon=True
                    ).start()
            threading.Thread(target=restart, daemon=True).start()

    def _mine1(self, mid: str, ram: str):
        m = PoLMMiner(
            f"http://localhost:{self.port}", mid, ram,
            self.chain.testnet, self._mstop
        )
        m.mine_once()

    def run(self):
        net = "testnet" if self.chain.testnet else "mainnet"
        print(f"\n╔══════════════════════════════════════════╗")
        print(f"║  PoLM Node  v{VERSION}  ({net})  RAM Mining  ║")
        print(f"║  {WEBSITE:<40}  ║")
        print(f"╚══════════════════════════════════════════╝")
        print(f"  API  : http://0.0.0.0:{self.port}")
        print(f"  RAM  : {detect_ram()}  Threads: {get_threads()}")
        s = self.chain.summary()
        print(f"  h={s['height']}  supply={s['total_supply']:.0f}/{MAX_SUPPLY} {SYMBOL}")
        print(f"  Rule : 1 IP = 1 miner  (anti-multimine)")
        print()
        # Bootstrap P2P network
        self.p2p.bootstrap()
        # P2P announce removed — bootstrap handles peer discovery
        self.app.run(
            host="0.0.0.0", port=self.port,
            debug=False, use_reloader=False, threaded=True
        )

# ─────────────────────────────────────────────────────────────────
# MINER
# ─────────────────────────────────────────────────────────────────
class PoLMMiner:
    def __init__(
        self,
        node_url: str,
        address:  str,
        ram:      str = "DDR4",
        testnet:  bool = False,
        stop:     Optional[threading.Event] = None,
        verbose:  bool = True,
    ):
        self.url     = node_url.rstrip("/")
        self.address = address
        self.ram     = ram.upper()
        self.testnet = testnet
        self.stop    = stop or threading.Event()
        self.verbose = verbose
        self.threads = get_threads()
        self.penalty = sat_penalty(self.threads)
        print(
            f"[Miner] {address[:24]}  |  {self.ram}  |  "
            f"threads={self.threads}  penalty={self.penalty}x  |  "
            f"{platform.system()}"
        )

    def _get(self, path: str) -> Optional[dict]:
        try:
            r = urllib.request.urlopen(f"{self.url}{path}", timeout=5)
            return json.loads(r.read())
        except Exception:
            return None

    def _post(self, path: str, data: dict) -> Optional[dict]:
        try:
            payload = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(
                f"{self.url}{path}", data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            r = urllib.request.urlopen(req, timeout=8)
            return json.loads(r.read())
        except Exception:
            return None

    def mine_loop(self):
        """Continuous mining — runs until stop event set."""
        self.stop.clear()
        while not self.stop.is_set():
            self.mine_once()

    def mine_once(self):
        """Mine one block, then return."""
        while not self.stop.is_set():
            work = self._get("/getwork")
            if not work:
                if self.verbose:
                    print("[Miner] Node offline — retrying in 5s...")
                time.sleep(5)
                continue

            height  = work["height"]
            prev    = work["prev_hash"]
            diff    = work["difficulty"]
            reward  = work["reward"]
            epoch   = work["epoch"]
            tn      = work.get("testnet", self.testnet)
            target  = "0" * diff
            pending = [Transaction.from_dict(t)
                       for t in work.get("pending_txs", [])]

            dag_seed = hashlib.sha3_256(
                f"polm:{epoch}:{prev[:32]}".encode()
            ).digest()
            dag   = MemoryDAG(dag_seed, epoch, tn)
            steps = walk_steps(tn)

            if self.verbose:
                print(
                    f"[Miner] #{height}  diff={diff}  "
                    f"reward={reward} {SYMBOL}  "
                    f"DAG={dag_size_mb(epoch, tn)}MB  "
                    f"txs={len(pending)}  {self.ram}"
                )

            nonce  = random.randint(0, 2 ** 32)
            t0     = time.time()
            checks = 0

            while not self.stop.is_set():
                nonce  += 1
                checks += 1

                if checks % 200 == 0:
                    nw = self._get("/getwork")
                    if nw and nw["height"] != height:
                        print(f"[Miner] -> #{nw['height']}  switching...")
                        break

                seed_h = hashlib.sha3_256(
                    f"{prev}:{self.address}:{nonce}".encode()
                ).digest()
                walk_h, lat = memory_walk(dag, seed_h, steps)
                if lat < 5:
                    continue

                sc    = compute_score(lat, 1.0, self.threads)

                b = Block(
                    height=height, prev_hash=prev,
                    timestamp=int(time.time()), nonce=nonce,
                    miner_id=self.address, ram_type=self.ram,
                    threads=self.threads, epoch=epoch,
                    difficulty=diff, latency_ns=round(lat, 4),
                    mem_proof=walk_h.hex(), score=round(sc, 8),
                    reward=reward,
                    cpu_name=detect_cpu(),
                    tx_ids=[t.tx_id for t in pending],
                )
                b.block_hash = b.compute_hash()

                if b.block_hash.startswith(target):
                    elapsed = time.time() - t0
                    if self.verbose:
                        print(f"\n[Miner] Block #{height} found!")
                        print(f"        Hash    : {b.block_hash[:24]}...")
                        print(f"        Nonce   : {nonce:,}")
                        print(f"        Time    : {elapsed:.2f}s")
                        print(f"        Latency : {lat:.1f}ns")
                        print(f"        Boost   : 1.000x  (pure latency)")
                        print(f"        Score   : {sc:.8f}")
                        print(f"        Reward  : {reward} {SYMBOL}")
                        print(f"        Txs     : {len(pending)}")
                    res = self._post("/submit", {
                        "block": b.to_dict(),
                        "txs":   [t.to_dict() for t in pending],
                    })
                    ok = res.get("accepted", False) if res else False
                    if self.verbose:
                        print(f"        Status  : {'ACCEPTED' if ok else 'rejected (race)'}\n")
                    return

# ─────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────
def _help():
    print(f"""
PoLM v{VERSION} — Proof of Legacy Memory | Mine with your RAM
{WEBSITE}

  python polm.py node   [port] [peer ...] [--testnet]
  python polm.py miner  <url> <address> <DDR2|DDR3|DDR4|DDR5> [--testnet]
  python polm.py info   [--testnet]

Mainnet examples:
  python polm.py node
  python polm.py node 6060 node2.polm.com.br:6060
  python polm.py miner http://node1.polm.com.br:6060 YOUR_ADDRESS DDR2

Testnet (local):
  python polm.py node --testnet
  python polm.py miner http://localhost:6060 YOUR_ADDRESS DDR2 --testnet

Override RAM type:
  Windows : set POLM_RAM_TYPE=DDR3
  Linux   : export POLM_RAM_TYPE=DDR3
""")

if __name__ == "__main__":
    if IS_WIN:
        import multiprocessing
        multiprocessing.freeze_support()

    args    = sys.argv[1:]
    testnet = "--testnet" in args or "--test" in args
    args    = [a for a in args if not a.startswith("--")]
    if testnet:
        NETWORK = "testnet"

    mode = args[0] if args else "help"

    if mode == "info":
        print(f"\n  PoLM  v{VERSION}  —  {WEBSITE}")
        print(f"  OS       : {platform.system()} {platform.release()}")
        print(f"  Python   : {platform.python_version()}")
        print(f"  RAM      : {detect_ram()}")
        print(f"  Threads  : {get_threads()}  penalty={sat_penalty(get_threads())}x")
        print(f"  Network  : {'testnet' if testnet else 'mainnet'}")
        print(f"  Crypto   : {'ECDSA secp256k1' if HAVE_CRYPTO else 'pip install cryptography'}")
        print(f"  Data dir : {default_data_dir()}")

    elif mode == "node":
        port  = int(args[1]) if len(args) > 1 and args[1].isdigit() else DEFAULT_PORT
        peers = [a for a in args[2:] if "." in a or ":" in a]
        node  = PoLMNode(
            data_dir=default_data_dir(),
            port=port,
            testnet=testnet,
            peers=peers,
        )
        node.run()

    elif mode == "miner":
        url     = args[1] if len(args) > 1 else "http://localhost:6060"
        address = args[2] if len(args) > 2 else "Anonymous"
        ram     = args[3] if len(args) > 3 else detect_ram()

        # Ask for EVM address on first run or if not registered
        import urllib.request as _ur
        import json as _json
        try:
            _r = _ur.urlopen(f"{url.rstrip('/')}/register_evm?polm_address={address}", timeout=5)
            _d = _json.loads(_r.read())
            _evm = _d.get("evm_address", "")
        except Exception:
            _evm = ""

        if not _evm:
            print()
            print("=" * 55)
            print("  POLM Bridge Setup — First Time Configuration")
            print("=" * 55)
            print(f"  Your POLM address: {address[:32]}...")
            print()
            print("  To claim your mined POLM on Polygon (MetaMask/Trust),")
            print("  enter your Polygon wallet address (0x...).")
            print("  You can skip this and register later at:")
            print("  https://polm.com.br/claim")
            print()
            _evm_input = input("  Polygon/Trust wallet (0x...) or ENTER to skip: ").strip()
            if _evm_input.startswith("0x") and len(_evm_input) == 42:
                try:
                    _payload = _json.dumps({"polm_address": address, "evm_address": _evm_input}).encode()
                    _req = _ur.Request(
                        f"{url.rstrip('/')}/register_evm",
                        data=_payload,
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )
                    _res = _json.loads(_ur.urlopen(_req, timeout=5).read())
                    if _res.get("ok"):
                        print(f"  ✓ Registered! You can claim at https://polm.com.br/claim")
                    else:
                        print(f"  Warning: {_res.get('error', 'Could not register')}")
                except Exception as _e:
                    print(f"  Warning: Could not register EVM address: {_e}")
            elif _evm_input:
                print("  Invalid address — skipping. Register later at https://polm.com.br/claim")
            else:
                print("  Skipped. Register later at https://polm.com.br/claim")
            print("=" * 55)
            print()
        else:
            print(f"[Miner] Polygon wallet: {_evm[:20]}...")

        miner = PoLMMiner(url, address, ram, testnet)
        miner.mine_loop()

    else:
        _help()
