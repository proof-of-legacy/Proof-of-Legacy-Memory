"""
polm_node.py — PoLM Full Node + Minerador
===========================================
Integra todos os módulos:
  • Blockchain (armazenamento + UTXO)
  • RAM Proof (consensus PoLM)
  • Rede P2P (peers + broadcast + sync)
  • Mempool (transações pendentes)
  • Minerador (threads de mineração)
  • API REST interna (opcional)

Uso:
    python3 polm_node.py                          # usa wallet.json existente
    python3 polm_node.py --address SEU_ENDERECO   # endereço explícito
    python3 polm_node.py --threads 2 --ram 128    # customização
    python3 polm_node.py --no-mine                # nó sem mineração
"""

import argparse
import hashlib
import json
import logging
import os
import platform
import random
import signal
import sys
import threading
import time
from collections import deque
from typing import Optional

from polm_core import (
    COIN, MAX_SUPPLY_SATS, MAX_MEMPOOL_SIZE, MAX_TX_PER_BLOCK,
    DEFAULT_PORT, WALLET_FILE, NETWORK_VERSION,
    block_reward_sats, hash_transaction, validate_tx_structure,
    hash_block_header, hash_meets_target, merkle_root,
    _is_coinbase,
)
from polm_chain import Blockchain
from polm_ram import (
    detect_ram_type, init_buffer, memory_storm,
    compute_ram_proof, verify_ram_proof_fast,
)
from polm_network import (
    PeerManager, Peer,
    MSG_VERSION, MSG_VERACK, MSG_BLOCK, MSG_TX,
    MSG_GETBLOCKS, MSG_BLOCKS, MSG_GETDATA,
    MSG_PING, MSG_PONG, MSG_GETPEERS, MSG_PEERS,
    MSG_REJECT,
)
from polm_wallet import PoLMWallet

log = logging.getLogger("PoLM.Node")

# ═══════════════════════════════════════════════════════════
# MEMPOOL
# ═══════════════════════════════════════════════════════════

class Mempool:
    """
    Pool de transações pendentes.
    Ordenadas por taxa (fee/byte) como Bitcoin.
    """

    def __init__(self):
        self._txs:  dict[str, dict] = {}
        self._lock  = threading.RLock()

    def add(self, tx: dict) -> tuple[bool, str]:
        ok, reason = validate_tx_structure(tx)
        if not ok:
            return False, reason

        txid = tx.get("txid") or hash_transaction(tx)

        with self._lock:
            if txid in self._txs:
                return False, "transação duplicada"

            if len(self._txs) >= MAX_MEMPOOL_SIZE:
                # Remove a tx com menor taxa
                min_txid = min(self._txs, key=lambda t: self._get_fee(self._txs[t]))
                if self._get_fee(tx) <= self._get_fee(self._txs[min_txid]):
                    return False, "mempool cheio — aumente a taxa"
                del self._txs[min_txid]

            self._txs[txid] = tx

        return True, txid

    def get_for_block(self, max_count: int = MAX_TX_PER_BLOCK) -> list[dict]:
        """Retorna transações ordenadas por taxa, prontas para inclusão em bloco."""
        with self._lock:
            txs = sorted(self._txs.values(), key=self._get_fee, reverse=True)
            return txs[:max_count - 1]   # -1 para reservar espaço para coinbase

    def remove(self, txids: list[str]) -> None:
        with self._lock:
            for txid in txids:
                self._txs.pop(txid, None)

    def __len__(self) -> int:
        return len(self._txs)

    def _get_fee(self, tx: dict) -> int:
        """Estima taxa de uma transação (diferença inputs - outputs)."""
        return tx.get("_fee", 0)

# ═══════════════════════════════════════════════════════════
# CONSTRUÇÃO DE BLOCO
# ═══════════════════════════════════════════════════════════

def build_candidate_block(
    chain: Blockchain,
    miner_address: str,
    txs: list[dict],
    ram_proof: dict,
    nonce: int = 0,
) -> dict:
    """Monta um bloco candidato para mineração."""
    tip    = chain.tip
    height = tip["height"] + 1

    # Calcula taxas totais
    total_fees = 0
    for tx in txs:
        total_fees += tx.get("_fee", 0)

    # Transação coinbase
    reward = block_reward_sats(height) + total_fees
    coinbase_tx = {
        "version": 1,
        "inputs": [{
            "txid":     "0" * 64,
            "vout":     -1,
            "coinbase": f"PoLM height={height} ts={int(time.time())}".encode().hex(),
            "sequence": 0xFFFFFFFF,
        }],
        "outputs": [{
            "value":   reward,
            "address": miner_address,
        }],
        "locktime": 0,
    }
    coinbase_tx["txid"] = hash_transaction(coinbase_tx)

    all_txs = [coinbase_tx] + txs
    txids   = [tx.get("txid") or hash_transaction(tx) for tx in all_txs]
    mr      = merkle_root(txids)

    block = {
        "version":      NETWORK_VERSION,
        "height":       height,
        "prev_hash":    tip["hash"],
        "merkle_root":  mr,
        "timestamp":    time.time(),
        "difficulty":   chain.get_next_difficulty(),
        "nonce":        nonce,
        "miner":        miner_address,
        "transactions": all_txs,
        "ram_proof":    ram_proof.get("work", 0),
        "ram_score":    ram_proof.get("score", 0.0),
        "ram_seed":     ram_proof.get("seed", 0),
        "ram_latency":  ram_proof.get("latency", 0.0),
        "ram_type":     ram_proof.get("ram_type", "AUTO"),
    }

    block["hash"] = hash_block_header(block)
    return block

# ═══════════════════════════════════════════════════════════
# NÓ PRINCIPAL
# ═══════════════════════════════════════════════════════════

class PoLMNode:
    """
    Nó completo da rede PoLM.
    Coordena mineração, rede, mempool e blockchain.
    """

    def __init__(
        self,
        miner_address: str,
        num_threads: int = 2,
        ram_mb: int = 256,
        port: int = DEFAULT_PORT,
        mine: bool = True,
    ):
        self.miner_address = miner_address
        self.num_threads   = num_threads
        self.mine_enabled  = mine
        self.port          = port

        self.chain   = Blockchain()
        self.mempool = Mempool()
        self.peers   = PeerManager(port)

        # RAM
        self.ram_type, self.ram_mult = detect_ram_type()
        self.buffer = init_buffer(ram_mb)

        # Estatísticas
        self._blocks_mined = 0
        self._start_time   = time.time()
        self._probe_times: deque = deque(maxlen=600)

        self._running = threading.Event()
        self._running.set()

    # ── Inicialização ────────────────────────────────────

    def start(self) -> None:
        log.info("Inicializando blockchain…")
        self.chain.initialize()

        log.info("Configurando handlers de rede…")
        self._register_net_handlers()

        log.info("Iniciando rede P2P…")
        self.peers.start()

        log.info("Iniciando sincronização inicial…")
        threading.Thread(target=self._initial_sync, daemon=True).start()

        if self.mine_enabled:
            log.info("Iniciando %d thread(s) de mineração…", self.num_threads)
            for i in range(self.num_threads):
                threading.Thread(
                    target=self._miner_loop,
                    daemon=True,
                    name=f"miner-{i}",
                ).start()

        threading.Thread(target=self._stats_loop, daemon=True).start()
        log.info("Nó PoLM iniciado.")

    # ── Mineração ────────────────────────────────────────

    def _miner_loop(self) -> None:
        name = threading.current_thread().name
        log.info("[%s] Thread de mineração pronta.", name)

        while self._running.is_set():
            # Verifica supply
            if self.chain.total_supply() >= MAX_SUPPLY_SATS:
                log.info("[%s] Supply máximo atingido — mineração encerrada.", name)
                break

            # Coleta transações do mempool
            pending_txs = self.mempool.get_for_block()

            # Executa prova de RAM
            seed      = random.randint(0, 2 ** 32 - 1)
            ram_proof = compute_ram_proof(seed, self.ram_mult, self.buffer)
            ram_proof["ram_type"] = self.ram_type

            tip_before = self.chain.tip

            # Monta candidato
            block    = build_candidate_block(
                self.chain, self.miner_address, pending_txs, ram_proof
            )
            target   = block["difficulty"]
            nonce    = 0
            ts_start = time.perf_counter()

            # Loop de nonces (PoW rápido)
            while self._running.is_set():
                # Cadeia mudou? (bloco recebido de peer) → recomeça
                if self.chain.tip != tip_before:
                    break

                block["nonce"] = nonce
                block["timestamp"] = time.time()
                block["hash"]  = hash_block_header(block)
                nonce         += 1

                with threading.Lock():
                    self._probe_times.append(time.perf_counter())

                if hash_meets_target(block["hash"], target):
                    # ✓ Bloco encontrado!
                    ok, reason = self.chain.add_block(block)
                    if ok:
                        self._blocks_mined += 1
                        tx_count = len(block["transactions"]) - 1

                        # Remove txs do mempool
                        txids = [
                            tx.get("txid") or hash_transaction(tx)
                            for tx in block["transactions"][1:]
                        ]
                        self.mempool.remove(txids)

                        elapsed = time.perf_counter() - ts_start
                        reward_polm = block_reward_sats(block["height"]) / COIN

                        log.info(
                            "✓ BLOCO %d | %s… | diff=%d | "
                            "RAM=%s mult=%.1f | score=%.2f | "
                            "txs=%d | recompensa=%.4f PoLM | %.2fs",
                            block["height"],
                            block["hash"][:14],
                            target,
                            self.ram_type, self.ram_mult,
                            ram_proof["score"],
                            tx_count,
                            reward_polm,
                            elapsed,
                        )

                        # Propaga
                        sent = self.peers.broadcast_block(block)
                        log.info("  Bloco propagado para %d peers.", sent)
                    else:
                        log.warning("Bloco minerado rejeitado: %s", reason)
                    break

    # ── Handlers de rede ─────────────────────────────────

    def _register_net_handlers(self) -> None:

        @self.peers.on(MSG_VERSION)
        def on_version(peer: Peer, payload: dict) -> None:
            peer.version = payload.get("version", "")
            peer.height  = payload.get("height", 0)
            peer.send(MSG_VERACK, {})
            peer.send(MSG_GETPEERS, {})
            # Solicita blocos que faltam
            known = [b["hash"] for b in self.chain.get_recent_blocks(10)]
            peer.send(MSG_GETBLOCKS, {"known": known})

        @self.peers.on(MSG_VERACK)
        def on_verack(peer: Peer, payload: dict) -> None:
            log.debug("Handshake completo com %s", peer.addr)

        @self.peers.on(MSG_BLOCK)
        def on_block(peer: Peer, payload: dict) -> None:
            block = payload.get("block")
            if not block:
                return

            ok, reason = self.chain.add_block(block)
            if ok:
                log.info("← Bloco %d de %s aceito", block.get("height", "?"), peer.addr)
                # Propaga para outros peers (exceto o remetente)
                for p in self.peers.connected_peers():
                    if p.addr != peer.addr:
                        p.send(MSG_BLOCK, {"block": block})
            else:
                if "duplicado" not in reason:
                    log.debug("Bloco de %s rejeitado: %s", peer.addr, reason)
                    peer.score -= 1
                    if peer.score < -10:
                        self.peers.ban_peer(peer.ip, f"muitos blocos inválidos: {reason}")

        @self.peers.on(MSG_TX)
        def on_tx(peer: Peer, payload: dict) -> None:
            tx = payload.get("tx")
            if not tx:
                return
            ok, reason = self.mempool.add(tx)
            if ok:
                for p in self.peers.connected_peers():
                    if p.addr != peer.addr:
                        p.send(MSG_TX, {"tx": tx})

        @self.peers.on(MSG_GETBLOCKS)
        def on_getblocks(peer: Peer, payload: dict) -> None:
            known   = set(payload.get("known", []))
            to_send = [
                b for b in self.chain.get_recent_blocks(50)
                if b["hash"] not in known
            ]
            for block in to_send[-20:]:  # máx 20 por vez
                peer.send(MSG_BLOCK, {"block": block})

        @self.peers.on(MSG_GETPEERS)
        def on_getpeers(peer: Peer, payload: dict) -> None:
            peer_list = [
                {"ip": p.ip, "port": p.port}
                for p in self.peers.known_peers()
                if p.ip != peer.ip
            ][:50]
            peer.send(MSG_PEERS, {"peers": peer_list})

        @self.peers.on(MSG_PEERS)
        def on_peers(peer: Peer, payload: dict) -> None:
            for entry in payload.get("peers", []):
                self.peers.add_peer(entry["ip"], entry.get("port", DEFAULT_PORT))

        @self.peers.on(MSG_PING)
        def on_ping(peer: Peer, payload: dict) -> None:
            peer.send(MSG_PONG, {"nonce": payload.get("nonce", 0)})

        @self.peers.on(MSG_PONG)
        def on_pong(peer: Peer, payload: dict) -> None:
            pass

    # ── Sync inicial ─────────────────────────────────────

    def _initial_sync(self) -> None:
        time.sleep(3)   # aguarda conexões
        known = [b["hash"] for b in self.chain.get_recent_blocks(10)]
        for peer in self.peers.connected_peers():
            peer.send(MSG_GETBLOCKS, {"known": known})

    # ── Estatísticas ─────────────────────────────────────

    def _stats_loop(self) -> None:
        while self._running.is_set():
            time.sleep(120)
            uptime   = int(time.time() - self._start_time)
            supply   = self.chain.total_supply() / COIN
            pct      = supply / (MAX_SUPPLY_SATS / COIN) * 100

            # Hashrate (provas por minuto)
            now    = time.perf_counter()
            recent = [t for t in self._probe_times if now - t <= 60]
            ppm    = len(recent)

            log.info(
                "📊 Altura=%d | Supply=%.0f PoLM (%.2f%%) | "
                "Minerados=%d | Mempool=%d | Peers=%d | "
                "Provas/min=%d | Uptime=%ds",
                self.chain.height,
                supply, pct,
                self._blocks_mined,
                len(self.mempool),
                self.peers.peer_count(),
                ppm,
                uptime,
            )

    # ── Shutdown ─────────────────────────────────────────

    def stop(self) -> None:
        log.info("Encerrando nó PoLM…")
        self._running.clear()

# ═══════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="PoLM Node — Proof of Legacy Memory Full Node",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python3 polm_node.py                         # nó completo com mineração
  python3 polm_node.py --threads 1 --ram 128   # hardware limitado
  python3 polm_node.py --no-mine               # nó sem mineração (relay)
  python3 polm_node.py --address ADDR          # endereço explícito
        """,
    )
    parser.add_argument("--address",  default="",            help="Endereço do minerador")
    parser.add_argument("--threads",  type=int, default=2,   help="Threads de mineração (padrão: 2)")
    parser.add_argument("--ram",      type=int, default=256, help="Tamanho do buffer RAM em MB (padrão: 256)")
    parser.add_argument("--port",     type=int, default=DEFAULT_PORT, help=f"Porta P2P (padrão: {DEFAULT_PORT})")
    parser.add_argument("--no-mine",  action="store_true",   help="Inicia sem mineração")
    parser.add_argument("--debug",    action="store_true",   help="Log nível DEBUG")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Carrega ou cria wallet
    if args.address:
        miner_address = args.address
    elif os.path.exists(WALLET_FILE):
        wallet = PoLMWallet.load()
        miner_address = wallet.primary_address
    else:
        log.info("Wallet não encontrada — criando nova…")
        wallet = PoLMWallet.create_new()
        wallet.save()
        miner_address = wallet.primary_address

    threads = max(1, min(args.threads, 8))

    # Banner
    if args.ram_type:
        from polm_ram import RAM_MULTIPLIERS
        ram_type = args.ram_type.upper()
        ram_mult = RAM_MULTIPLIERS.get(ram_type, 1.0)
    else:
        ram_type, ram_mult = detect_ram_type()
    print("\n" + "═" * 62)
    print("   ██████╗  ██████╗ ██╗     ███╗   ███╗")
    print("   ██╔══██╗██╔═══██╗██║     ████╗ ████║")
    print("   ██████╔╝██║   ██║██║     ██╔████╔██║")
    print("   ██╔═══╝ ██║   ██║██║     ██║╚██╔╝██║")
    print("   ██║     ╚██████╔╝███████╗██║ ╚═╝ ██║")
    print("   ╚═╝      ╚═════╝ ╚══════╝╚═╝     ╚═╝")
    print("   Proof of Legacy Memory  •  v1.0")
    print("═" * 62)
    print(f"   Endereço  : {miner_address}")
    print(f"   RAM       : {ram_type}  (mult={ram_mult:.2f}x)")
    print(f"   Buffer    : {args.ram} MB")
    print(f"   CPU       : {platform.processor() or platform.machine()}")
    print(f"   Cores     : {os.cpu_count()}")
    print(f"   Threads   : {threads}")
    print(f"   Porta P2P : {args.port}")
    print(f"   Minerando : {'SIM' if not args.no_mine else 'NÃO (modo relay)'}")
    print("═" * 62 + "\n")

    node = PoLMNode(
        miner_address=miner_address,
        num_threads=threads,
        ram_mb=args.ram,
        port=args.port,
        mine=not args.no_mine,
    )

    def _shutdown(sig, frame):
        print("\n  Encerrando PoLM Node…")
        node.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    node.start()

    # Mantém processo principal vivo
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        _shutdown(None, None)


if __name__ == "__main__":
    main()
