"""
PoLM-X v2 — Full Node
P2P networking + mempool + REST API
"""

import hashlib
import time
import json
import os
import socket
import threading
import struct
import random
from typing import List, Optional, Dict, Set
from flask import Flask, jsonify, request
from polm_x_core import (
    PoLMChain, PoLMXMiner, Block, BlockHeader, Transaction,
    RAMType, POLM_VERSION, COIN_SYMBOL, MAX_SUPPLY,
    validate_full_chain, block_reward, get_epoch, get_min_ram_mb,
    get_dag_size_mb, detect_ram_type, get_cpu_threads,
    LEGACY_BOOST, saturation_penalty,
)
from dataclasses import asdict

# ─────────────────────────────────────────────
# MEMPOOL
# ─────────────────────────────────────────────
class Mempool:
    def __init__(self, max_size: int = 10_000):
        self._txs: Dict[str, Transaction] = {}
        self._lock = threading.Lock()
        self.max_size = max_size

    def add(self, tx: Transaction) -> bool:
        with self._lock:
            if tx.tx_id in self._txs:
                return False
            if len(self._txs) >= self.max_size:
                return False
            self._txs[tx.tx_id] = tx
            return True

    def get_top(self, n: int = 50) -> List[Transaction]:
        with self._lock:
            # sort by fee descending
            return sorted(self._txs.values(), key=lambda t: t.fee, reverse=True)[:n]

    def remove(self, tx_ids: List[str]):
        with self._lock:
            for tid in tx_ids:
                self._txs.pop(tid, None)

    def size(self) -> int:
        return len(self._txs)

    def all_ids(self) -> List[str]:
        return list(self._txs.keys())

# ─────────────────────────────────────────────
# P2P PEER MANAGER
# ─────────────────────────────────────────────
class PeerManager:
    """Simple peer tracker."""
    def __init__(self, bootstrap_peers: List[str] = None):
        self.peers: Set[str] = set(bootstrap_peers or [])
        self._lock = threading.Lock()

    def add_peer(self, addr: str):
        with self._lock:
            self.peers.add(addr)

    def remove_peer(self, addr: str):
        with self._lock:
            self.peers.discard(addr)

    def get_peers(self) -> List[str]:
        with self._lock:
            return list(self.peers)

    def count(self) -> int:
        return len(self.peers)

# ─────────────────────────────────────────────
# POLM-X NODE
# ─────────────────────────────────────────────
class PoLMXNode:
    """
    Full PoLM-X node:
    - blockchain storage & validation
    - mempool
    - peer manager
    - REST API (Flask)
    - optional integrated miner
    """

    def __init__(
        self,
        node_id: str,
        chain_file: str = "polmx_chain.json",
        api_host: str = "0.0.0.0",
        api_port: int = 6060,
        bootstrap_peers: Optional[List[str]] = None,
        testnet: bool = True,
    ):
        self.node_id   = node_id
        self.api_host  = api_host
        self.api_port  = api_port
        self.testnet   = testnet

        self.chain   = PoLMChain(chain_file=chain_file, testnet=testnet)
        self.mempool = Mempool()
        self.peers   = PeerManager(bootstrap_peers or [])
        self.miner: Optional[PoLMXMiner] = None
        self._mining_thread: Optional[threading.Thread] = None

        self.app = Flask(f"polmx-node-{node_id}")
        self._register_routes()

        print(f"\n[Node] PoLM-X Node '{node_id}' initialized")
        print(f"[Node] API: http://{api_host}:{api_port}")
        print(f"[Node] Chain height: {self.chain.height}")

    # ─── ROUTES ───────────────────────────────
    def _register_routes(self):
        app = self.app

        @app.route("/", methods=["GET"])
        def index():
            return jsonify({
                "node":    self.node_id,
                "version": POLM_VERSION,
                "chain":   self.chain.summary(),
                "mempool": self.mempool.size(),
                "peers":   self.peers.count(),
                "mining":  self._mining_thread is not None and self._mining_thread.is_alive(),
            })

        @app.route("/chain", methods=["GET"])
        def get_chain():
            limit = int(request.args.get("limit", 20))
            offset = int(request.args.get("offset", 0))
            blocks = self.chain.chain[::-1][offset:offset+limit]
            return jsonify([b.to_dict() for b in blocks])

        @app.route("/block/<int:height>", methods=["GET"])
        def get_block(height):
            if height < 0 or height > self.chain.height:
                return jsonify({"error": "block not found"}), 404
            return jsonify(self.chain.chain[height].to_dict())

        @app.route("/block/hash/<hash_str>", methods=["GET"])
        def get_block_by_hash(hash_str):
            for blk in self.chain.chain:
                if blk.block_hash == hash_str:
                    return jsonify(blk.to_dict())
            return jsonify({"error": "not found"}), 404

        @app.route("/tx/submit", methods=["POST"])
        def submit_tx():
            data = request.json
            try:
                tx = Transaction(**data)
                ok = self.mempool.add(tx)
                return jsonify({"accepted": ok, "tx_id": tx.tx_id})
            except Exception as e:
                return jsonify({"error": str(e)}), 400

        @app.route("/mempool", methods=["GET"])
        def get_mempool():
            txs = self.mempool.get_top(50)
            return jsonify({
                "size": self.mempool.size(),
                "top_txs": [asdict(tx) for tx in txs]
            })

        @app.route("/balance/<address>", methods=["GET"])
        def get_balance(address):
            return jsonify({
                "address": address,
                "balance": self.chain.get_balance(address),
                "symbol":  COIN_SYMBOL,
            })

        @app.route("/peers", methods=["GET"])
        def get_peers():
            return jsonify({"peers": self.peers.get_peers()})

        @app.route("/peers/add", methods=["POST"])
        def add_peer():
            data = request.json
            self.peers.add_peer(data.get("address", ""))
            return jsonify({"peers": self.peers.get_peers()})

        @app.route("/mine/start", methods=["POST"])
        def mine_start():
            data = request.json or {}
            miner_id   = data.get("miner_id", self.node_id)
            ram_type_s = data.get("ram_type", "")
            try:
                ram_type = RAMType(ram_type_s) if ram_type_s else detect_ram_type()
            except Exception:
                ram_type = RAMType.UNKNOWN
            self._start_miner(miner_id, ram_type)
            return jsonify({"mining": True, "miner_id": miner_id, "ram": ram_type.value})

        @app.route("/mine/stop", methods=["POST"])
        def mine_stop():
            self._stop_miner()
            return jsonify({"mining": False})

        @app.route("/validate", methods=["GET"])
        def validate():
            ok, errors = validate_full_chain(self.chain)
            return jsonify({"valid": ok, "errors": errors})

        @app.route("/network/info", methods=["GET"])
        def network_info():
            tip = self.chain.tip.header
            epoch = get_epoch(tip.height)
            return jsonify({
                "height":          self.chain.height,
                "epoch":           epoch,
                "min_ram_gb":      get_min_ram_mb(epoch) // 1024,
                "dag_size_gb":     get_dag_size_mb(epoch) // 1024,
                "difficulty":      self.chain.difficulty.current,
                "next_reward":     block_reward(tip.height + 1),
                "total_supply":    round(self.chain.total_supply(), 4),
                "max_supply":      MAX_SUPPLY,
                "legacy_boosts":   {k.value: v for k, v in LEGACY_BOOST.items()},
            })

        @app.route("/receive_block", methods=["POST"])
        def receive_block():
            """P2P endpoint: accept a mined block from a peer."""
            data = request.json
            try:
                txs  = [Transaction(**tx) for tx in data.pop("transactions")]
                bh   = data.pop("block_hash")
                hdr  = BlockHeader(**data)
                blk  = Block(header=hdr, transactions=txs, block_hash=bh)
                ok, reason = self.chain.add_block(blk)
                return jsonify({"accepted": ok, "reason": reason})
            except Exception as e:
                return jsonify({"error": str(e)}), 400

    # ─── MINER CONTROL ────────────────────────
    def _start_miner(self, miner_id: str, ram_type: RAMType):
        if self._mining_thread and self._mining_thread.is_alive():
            return
        self.miner = PoLMXMiner(
            self.chain, miner_id=miner_id, ram_type=ram_type,
            threads=get_cpu_threads(), verbose=True
        )
        self._mining_thread = threading.Thread(
            target=self._mine_loop, daemon=True
        )
        self._mining_thread.start()
        print(f"[Node] Mining started: {miner_id} ({ram_type.value})")

    def _stop_miner(self):
        if self.miner:
            self.miner.stop()
        print("[Node] Mining stopped")

    def _mine_loop(self):
        while self.miner and not self.miner._stop.is_set():
            pending = self.mempool.get_top(50)
            blk = self.miner.mine_block(pending_txs=pending)
            if blk:
                ok, reason = self.chain.add_block(blk)
                if ok:
                    mined_ids = [tx.tx_id for tx in blk.transactions]
                    self.mempool.remove(mined_ids)
                    self._broadcast_block(blk)

    def _broadcast_block(self, blk: Block):
        """Broadcast mined block to all peers."""
        import urllib.request
        payload = json.dumps(blk.to_dict()).encode()
        for peer in self.peers.get_peers():
            try:
                req = urllib.request.Request(
                    f"http://{peer}/receive_block",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                urllib.request.urlopen(req, timeout=5)
            except Exception:
                pass

    def run(self, debug: bool = False):
        print(f"[Node] Starting REST API on port {self.api_port}…")
        self.app.run(host=self.api_host, port=self.api_port, debug=debug)


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    port     = int(sys.argv[1]) if len(sys.argv) > 1 else 6060
    node_id  = f"polmx-node-{port}"
    node     = PoLMXNode(
        node_id=node_id,
        chain_file=f"polmx_chain_{port}.json",
        api_port=port,
        testnet=True,
    )
    node.run()
