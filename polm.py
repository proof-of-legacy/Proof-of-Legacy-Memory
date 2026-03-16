"""
PoLM Coin — Blockchain Central + Pool de Mineração
Arquitetura simples: 1 nó central + N mineradores
Supply: 32,000,000 POLM
"""

import hashlib, time, json, os, threading, random
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict
from enum import Enum
from flask import Flask, jsonify, request

# ─────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────
VERSION          = "3.0.0"
SYMBOL           = "POLM"
MAX_SUPPLY       = 32_000_000
INITIAL_REWARD   = 5.0
HALVING_BLOCKS   = 4 * 365 * 24 * 120   # ~4 anos
BLOCK_TIME       = 30                    # segundos alvo
DIFF_WINDOW      = 144                   # blocos para retarget
EPOCH_BLOCKS     = 100_000
DAG_MB_BASE      = 4                     # MB em testnet
WALK_STEPS       = 500                   # testnet DDR4 baseline (100000 em mainnet)
# Passos adaptativos por tipo de RAM — DDR2 faz menos passos, mais nonces/s
WALK_STEPS_BY_RAM = {
    "DDR2": 80,   # rápido — compensa latência alta
    "DDR3": 150,  # médio
    "DDR4": 500,  # baseline
    "DDR5": 700,  # mais pesado — penaliza RAM rápida
}
GENESIS_TIME     = 1741000000

# ─────────────────────────────────────────────
# RAM BOOST
# ─────────────────────────────────────────────
class RAMType(Enum):
    DDR2 = "DDR2"; DDR3 = "DDR3"
    DDR4 = "DDR4"; DDR5 = "DDR5"
    UNKNOWN = "DDR4"

# Boost calibrado para DDR2 ≈ DDR4 (dados reais testnet Mar 2026)
# DDR2 ~6800ns, DDR4 ~1200ns → ratio ~5.7x compensado pelo boost
BOOST = {
    RAMType.DDR2: 10.00, RAMType.DDR3: 5.00,
    RAMType.DDR4: 1.00, RAMType.DDR5: 0.00,
    RAMType.UNKNOWN: 1.00,
}

# Penalidade de threads — freia CPUs modernas com muitos cores
# DDR2 tipicamente tem 2 threads → 1.00x (sem penalidade)
# DDR4 16 threads → 0.65x
def sat_penalty(threads: int) -> float:
    if threads <= 2:  return 1.00
    if threads <= 4:  return 0.90
    if threads <= 8:  return 0.80
    if threads <= 16: return 0.65
    return 0.50

# ─────────────────────────────────────────────
# DAG + MEMORY WALK
# ─────────────────────────────────────────────
class DAG:
    def __init__(self, seed: bytes, size_mb: int = DAG_MB_BASE):
        self.size = size_mb * 1024 * 1024
        buf, cur = [], hashlib.sha3_256(seed).digest()
        needed = self.size
        while needed > 0:
            blk = hashlib.sha3_512(cur).digest()
            buf.append(blk); needed -= len(blk); cur = blk
        self._buf = bytearray(b"".join(buf)[:self.size])

    def read(self, pos: int) -> bytes:
        idx = pos % (self.size - 32)
        return bytes(self._buf[idx:idx+32])

def memory_walk(dag: DAG, seed: bytes, steps: int = WALK_STEPS):
    h = seed
    pos = int.from_bytes(h[:8], "little") % dag.size
    t0 = time.perf_counter_ns()
    for _ in range(steps):
        mem = dag.read(pos)
        h   = hashlib.sha3_256(h + mem).digest()
        pos = int.from_bytes(h[:8], "little") % dag.size
    latency = (time.perf_counter_ns() - t0) / steps
    return h, latency

# ─────────────────────────────────────────────
# BLOCKCHAIN
# ─────────────────────────────────────────────
def block_reward(height: int) -> float:
    h = height // HALVING_BLOCKS
    return 0.0 if h >= 64 else INITIAL_REWARD / (2 ** h)

def get_epoch(height: int) -> int:
    return height // EPOCH_BLOCKS

@dataclass
class Block:
    height:      int
    prev_hash:   str
    timestamp:   int
    nonce:       int
    miner_id:    str
    ram_type:    str
    threads:     int
    epoch:       int
    difficulty:  int
    latency_ns:  float
    mem_proof:   str
    score:       float
    reward:      float
    block_hash:  str = ""

    def compute_hash(self) -> str:
        raw = (f"{self.height}|{self.prev_hash}|{self.timestamp}|"
               f"{self.nonce}|{self.miner_id}|{self.ram_type}|"
               f"{self.threads}|{self.epoch}|{self.difficulty}|"
               f"{self.latency_ns:.2f}|{self.mem_proof}|{self.score:.4f}|{self.reward}")
        return hashlib.sha3_256(raw.encode()).hexdigest()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Block":
        return cls(**d)

class Blockchain:
    def __init__(self, chain_file: str = "polm_chain.json"):
        self.file   = chain_file
        self.chain: List[Block] = []
        self._lock  = threading.Lock()
        self._diff  = 4
        self._load_or_genesis()

    def _genesis(self):
        b = Block(
            height=0, prev_hash="0"*64, timestamp=GENESIS_TIME,
            nonce=0, miner_id="GENESIS", ram_type="DDR4", threads=1,
            epoch=0, difficulty=self._diff, latency_ns=0.0,
            mem_proof="0"*64, score=0.0, reward=INITIAL_REWARD,
        )
        b.block_hash = b.compute_hash()
        self.chain.append(b)
        self._save()
        print(f"[Chain] Genesis: {b.block_hash[:16]}…")

    def _save(self):
        with open(self.file, "w") as f:
            json.dump([b.to_dict() for b in self.chain], f)

    def _load_or_genesis(self):
        if os.path.exists(self.file):
            with open(self.file) as f:
                self.chain = [Block.from_dict(d) for d in json.load(f)]
            self._diff = self.chain[-1].difficulty
            print(f"[Chain] Loaded {len(self.chain)} blocks, height={self.height}")
        else:
            self._genesis()

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

    def retarget(self):
        if len(self.chain) < 2 or len(self.chain) % DIFF_WINDOW != 0:
            return
        window = self.chain[-DIFF_WINDOW:]
        elapsed  = window[-1].timestamp - window[0].timestamp
        expected = BLOCK_TIME * (DIFF_WINDOW - 1)
        if elapsed == 0: return
        ratio    = max(0.75, min(1.25, expected / elapsed))
        self._diff = max(1, round(self._diff * ratio))
        print(f"[Chain] Difficulty retarget → {self._diff}")

    def add_block(self, b: Block) -> tuple:
        with self._lock:
            if b.height != self.height + 1:
                return False, f"height mismatch (got {b.height}, want {self.height+1})"
            if b.prev_hash != self.tip.block_hash:
                return False, "prev_hash mismatch"
            if not b.block_hash.startswith(self.target()):
                return False, "insufficient PoW"
            if b.compute_hash() != b.block_hash:
                return False, "hash mismatch"
            if b.latency_ns < 5:
                return False, "latency too low (cache exploit?)"
            reward = block_reward(b.height)
            if abs(b.reward - reward) > 0.0001:
                return False, f"wrong reward (got {b.reward}, want {reward})"
            self.chain.append(b)
            self.retarget()
            self._save()
            return True, "ok"

    def total_supply(self) -> float:
        return sum(b.reward for b in self.chain)

    def get_balance(self, addr: str) -> float:
        # simplified: sum rewards for miner
        return sum(b.reward for b in self.chain if b.miner_id == addr)

    def summary(self) -> dict:
        epoch = get_epoch(self.height)
        return {
            "version":      VERSION,
            "height":       self.height,
            "tip_hash":     self.tip.block_hash,
            "difficulty":   self._diff,
            "epoch":        epoch,
            "total_supply": round(self.total_supply(), 4),
            "max_supply":   MAX_SUPPLY,
            "next_reward":  block_reward(self.height + 1),
            "block_time":   BLOCK_TIME,
        }

# ─────────────────────────────────────────────
# MINERADOR (roda em qualquer PC)
# ─────────────────────────────────────────────
class Miner:
    def __init__(self, node_url: str, miner_id: str,
                 ram_type: RAMType = RAMType.DDR4, threads: int = 4):
        self.node_url  = node_url.rstrip("/")
        self.miner_id  = miner_id
        self.ram_type  = ram_type
        self.threads   = threads
        self.boost     = BOOST[ram_type]
        self.penalty   = sat_penalty(threads)
        self._stop     = threading.Event()
        print(f"[Miner] {miner_id} | {ram_type.value} | "
              f"boost={self.boost}x | threads={threads} | penalty={self.penalty}x")

    def _get_work(self) -> Optional[dict]:
        import urllib.request
        try:
            r = urllib.request.urlopen(f"{self.node_url}/getwork", timeout=5)
            return json.loads(r.read())
        except:
            return None

    def _submit(self, block_dict: dict) -> bool:
        import urllib.request
        try:
            payload = json.dumps(block_dict).encode()
            req = urllib.request.Request(
                f"{self.node_url}/submit",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            r = urllib.request.urlopen(req, timeout=5)
            result = json.loads(r.read())
            return result.get("accepted", False)
        except:
            return False

    def mine_loop(self):
        self._stop.clear()
        dag = None
        last_height = -1

        while not self._stop.is_set():
            work = self._get_work()
            if not work:
                print("[Miner] Node offline, retrying in 5s...")
                time.sleep(5)
                continue

            height     = work["height"]
            prev_hash  = work["prev_hash"]
            difficulty = work["difficulty"]
            reward     = work["reward"]
            target     = "0" * difficulty
            epoch      = get_epoch(height)

            # rebuild DAG only when height/epoch changes
            if height != last_height:
                seed = hashlib.sha3_256(
                    f"polm:{epoch}:{prev_hash[:32]}".encode()
                ).digest()
                dag = DAG(seed, size_mb=DAG_MB_BASE)
                last_height = height
                print(f"[Miner] Mining block #{height} | diff={difficulty} | "
                      f"reward={reward} {SYMBOL} | RAM={self.ram_type.value}")

            nonce  = random.randint(0, 2**32)
            t0     = time.time()
            checks = 0  # refresh work every N attempts

            while not self._stop.is_set():
                nonce  += 1
                checks += 1

                # refresh work every 50 attempts — picks up new height fast
                if checks % 50 == 0:
                    new_work = self._get_work()
                    if new_work and new_work["height"] != height:
                        print(f"[Miner] ↻ New block #{new_work['height']} detected, switching...")
                        break  # restart outer loop with new work

                seed_hash = hashlib.sha3_256(
                    f"{prev_hash}:{self.miner_id}:{nonce}".encode()
                ).digest()
                steps = WALK_STEPS_BY_RAM.get(self.ram_type.value, WALK_STEPS)
                walk_hash, latency_ns = memory_walk(dag, seed_hash, steps=steps)

                if latency_ns < 5:
                    continue

                score = nonce * self.boost * self.penalty

                b = Block(
                    height=height, prev_hash=prev_hash,
                    timestamp=int(time.time()), nonce=nonce,
                    miner_id=self.miner_id, ram_type=self.ram_type.value,
                    threads=self.threads, epoch=epoch,
                    difficulty=difficulty, latency_ns=round(latency_ns, 2),
                    mem_proof=walk_hash.hex(), score=round(score, 4),
                    reward=reward,
                )
                b.block_hash = b.compute_hash()

                if b.block_hash.startswith(target):
                    elapsed = time.time() - t0
                    print(f"\n[Miner] ✓ Block #{height} found!")
                    print(f"        Hash    : {b.block_hash[:24]}…")
                    print(f"        Nonce   : {nonce:,}")
                    print(f"        Time    : {elapsed:.2f}s")
                    print(f"        Latency : {latency_ns:.1f}ns")
                    print(f"        Score   : {score:.0f}")
                    print(f"        Reward  : {reward} {SYMBOL}")
                    if self._submit(b.to_dict()):
                        print(f"        Status  : ✅ ACEITO\n")
                    else:
                        print(f"        Status  : ⚠ rejeitado (outro minerou primeiro)\n")
                    break  # pega novo trabalho

    def stop(self):
        self._stop.set()

# ─────────────────────────────────────────────
# NÓ CENTRAL (roda só no H610M)
# ─────────────────────────────────────────────
class PoLMNode:
    def __init__(self, chain_file: str = "polm_chain.json",
                 host: str = "0.0.0.0", port: int = 6060):
        self.chain = Blockchain(chain_file)
        self.app   = Flask("polm-node")
        self.host  = host
        self.port  = port
        self._register_routes()

    def _register_routes(self):
        app = self.app

        @app.route("/")
        def index():
            return jsonify(self.chain.summary())

        @app.route("/getwork")
        def getwork():
            """Mineradores chamam isso para pegar trabalho atual."""
            tip = self.chain.tip
            return jsonify({
                "height":    tip.height + 1,
                "prev_hash": tip.block_hash,
                "difficulty": self.chain.difficulty,
                "reward":    block_reward(tip.height + 1),
                "epoch":     get_epoch(tip.height + 1),
                "target":    self.chain.target(),
            })

        @app.route("/submit", methods=["POST"])
        def submit():
            """Mineradores enviam bloco encontrado aqui."""
            try:
                b = Block.from_dict(request.json)
                ok, reason = self.chain.add_block(b)
                if ok:
                    print(f"[Node] ✅ Block #{b.height} by {b.miner_id[:20]} "
                          f"| {b.ram_type} | {b.latency_ns:.0f}ns | score:{b.score:.0f}")
                return jsonify({"accepted": ok, "reason": reason})
            except Exception as e:
                return jsonify({"accepted": False, "reason": str(e)}), 400

        @app.route("/chain")
        def get_chain():
            limit  = int(request.args.get("limit", 20))
            offset = int(request.args.get("offset", 0))
            blocks = self.chain.chain[::-1][offset:offset+limit]
            return jsonify([b.to_dict() for b in blocks])

        @app.route("/block/<int:h>")
        def get_block(h):
            if 0 <= h <= self.chain.height:
                return jsonify(self.chain.chain[h].to_dict())
            return jsonify({"error": "not found"}), 404

        @app.route("/balance/<addr>")
        def balance(addr):
            return jsonify({
                "address": addr,
                "balance": self.chain.get_balance(addr),
                "symbol":  SYMBOL,
            })

        @app.route("/miners")
        def miners():
            """Mostra estatísticas por minerador."""
            stats: Dict[str, dict] = {}
            for b in self.chain.chain[1:]:
                m = b.miner_id
                if m not in stats:
                    stats[m] = {"blocks": 0, "reward": 0.0, "ram": b.ram_type,
                                "avg_latency": [], "avg_score": []}
                stats[m]["blocks"]  += 1
                stats[m]["reward"]  += b.reward
                stats[m]["avg_latency"].append(b.latency_ns)
                stats[m]["avg_score"].append(b.score)
            for m in stats:
                lats = stats[m]["avg_latency"]
                scrs = stats[m]["avg_score"]
                stats[m]["avg_latency"] = round(sum(lats)/len(lats), 1) if lats else 0
                stats[m]["avg_score"]   = round(sum(scrs)/len(scrs), 0) if scrs else 0
            return jsonify(stats)

    def run(self):
        print(f"\n[Node] PoLM v{VERSION} — http://{self.host}:{self.port}")
        print(f"[Node] Chain height: {self.chain.height} | "
              f"Supply: {self.chain.total_supply():.0f}/{MAX_SUPPLY} {SYMBOL}")
        self.app.run(host=self.host, port=self.port)


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "node"

    if mode == "node":
        # Roda o nó central — só no H610M
        node = PoLMNode(chain_file="polm_chain.json", port=6060)
        node.run()

    elif mode == "miner":
        # Roda o minerador — em qualquer PC
        # Uso: python3 polm.py miner <NODE_IP> <MINER_ID> <RAM_TYPE>
        node_ip  = sys.argv[2] if len(sys.argv) > 2 else "192.168.0.103"
        miner_id = sys.argv[3] if len(sys.argv) > 3 else "POLM_Miner"
        ram_str  = sys.argv[4] if len(sys.argv) > 4 else "DDR4"
        try:
            ram = RAMType(ram_str)
        except:
            ram = RAMType.DDR4
        import os
        threads = os.cpu_count() or 2
        m = Miner(
            node_url=f"http://{node_ip}:6060",
            miner_id=miner_id,
            ram_type=ram,
            threads=threads,
        )
        m.mine_loop()
