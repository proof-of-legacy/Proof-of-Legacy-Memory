"""
polm_network.py — Camada P2P do PoLM
======================================
Protocolo de comunicação entre nós da rede.

Mensagens suportadas:
  VERSION   — handshake inicial + troca de informações do nó
  VERACK    — confirmação de handshake
  GETBLOCKS — pede lista de hashes de blocos
  BLOCKS    — responde com lista de hashes
  GETDATA   — pede bloco específico por hash
  BLOCK     — envia um bloco completo
  TX        — anuncia transação
  GETTX     — pede transação específica
  PING/PONG — keep-alive
  GETPEERS  — pede lista de peers conhecidos
  PEERS     — envia lista de peers

Proteções:
  • Rate limiting por IP (máx 100 msg/s)
  • Banimento temporário de peers maliciosos
  • Tamanho máximo de mensagem: 2 MB
  • Timeout em todas as operações de rede
  • Blacklist de IPs banidos
"""

import json
import logging
import os
import random
import socket
import struct
import threading
import time
from collections import defaultdict, deque
from typing import Callable, Optional

from polm_core import (
    NETWORK_MAGIC, DEFAULT_PORT, MAX_PEERS,
    PROTOCOL_VERSION, PEERS_FILE, NETWORK_VERSION,
)

log = logging.getLogger("PoLM.Net")

# ═══════════════════════════════════════════════════════════
# PROTOCOLO DE MENSAGENS
# ═══════════════════════════════════════════════════════════

MSG_VERSION   = "version"
MSG_VERACK    = "verack"
MSG_GETBLOCKS = "getblocks"
MSG_BLOCKS    = "blocks"
MSG_GETDATA   = "getdata"
MSG_BLOCK     = "block"
MSG_TX        = "tx"
MSG_GETTX     = "gettx"
MSG_PING      = "ping"
MSG_PONG      = "pong"
MSG_GETPEERS  = "getpeers"
MSG_PEERS     = "peers"
MSG_REJECT    = "reject"

MAX_MESSAGE_SIZE = 2 * 1024 * 1024   # 2 MB
HEADER_SIZE      = 12                 # magic(4) + cmd(4) + length(4)

# Rate limiting
RATE_WINDOW  = 1.0    # janela em segundos
RATE_MAX_MSG = 100    # máximo de mensagens por janela
BAN_DURATION = 3600   # segundos de banimento


def encode_message(cmd: str, payload: dict) -> bytes:
    """Codifica uma mensagem do protocolo PoLM."""
    cmd_bytes  = cmd.encode()[:4].ljust(4, b"\x00")
    body       = json.dumps(payload, separators=(",", ":")).encode()
    length     = len(body)
    header     = struct.pack(">I", NETWORK_MAGIC) + cmd_bytes + struct.pack(">I", length)
    return header + body


def decode_message(data: bytes) -> tuple[str, dict]:
    """Decodifica uma mensagem do protocolo PoLM."""
    if len(data) < HEADER_SIZE:
        raise ValueError("Mensagem muito curta")

    magic, = struct.unpack(">I", data[:4])
    if magic != NETWORK_MAGIC:
        raise ValueError(f"Magic inválido: {magic:#010x}")

    cmd    = data[4:8].rstrip(b"\x00").decode(errors="replace")
    length, = struct.unpack(">I", data[8:12])

    if length > MAX_MESSAGE_SIZE:
        raise ValueError(f"Mensagem muito grande: {length} bytes")

    body = data[HEADER_SIZE: HEADER_SIZE + length]
    if len(body) < length:
        raise ValueError("Mensagem incompleta")

    payload = json.loads(body.decode())
    return cmd, payload

# ═══════════════════════════════════════════════════════════
# PEER
# ═══════════════════════════════════════════════════════════

class Peer:
    """Representa uma conexão com um peer."""

    def __init__(self, ip: str, port: int = DEFAULT_PORT):
        self.ip:         str            = ip
        self.port:       int            = port
        self.connected:  bool           = False
        self.version:    str            = ""
        self.height:     int            = 0
        self.last_seen:  float          = 0
        self.score:      int            = 0      # pontuação de confiança
        self._sock:      Optional[socket.socket] = None
        self._lock       = threading.Lock()

    @property
    def addr(self) -> str:
        return f"{self.ip}:{self.port}"

    def connect(self, timeout: float = 5.0) -> bool:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect((self.ip, self.port))
            s.settimeout(30)
            self._sock       = s
            self.connected   = True
            self.last_seen   = time.time()
            return True
        except Exception as e:
            log.debug("Não foi possível conectar a %s: %s", self.addr, e)
            return False

    def disconnect(self) -> None:
        self.connected = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def send(self, cmd: str, payload: dict) -> bool:
        if not self.connected or not self._sock:
            return False
        try:
            msg = encode_message(cmd, payload)
            with self._lock:
                self._sock.sendall(msg)
            return True
        except Exception as e:
            log.debug("Erro ao enviar para %s: %s", self.addr, e)
            self.disconnect()
            return False

    def recv_message(self) -> Optional[tuple[str, dict]]:
        """Recebe uma mensagem completa (bloqueante com timeout)."""
        if not self._sock:
            return None
        try:
            header = self._recv_exact(HEADER_SIZE)
            if not header:
                return None

            magic, = struct.unpack(">I", header[:4])
            if magic != NETWORK_MAGIC:
                return None

            cmd    = header[4:8].rstrip(b"\x00").decode(errors="replace")
            length, = struct.unpack(">I", header[8:12])

            if length > MAX_MESSAGE_SIZE:
                log.warning("%s enviou mensagem de %d bytes — ignorando", self.addr, length)
                return None

            body    = self._recv_exact(length)
            payload = json.loads(body.decode())
            self.last_seen = time.time()
            return cmd, payload

        except (json.JSONDecodeError, ValueError) as e:
            log.debug("Mensagem inválida de %s: %s", self.addr, e)
            return None
        except Exception:
            self.disconnect()
            return None

    def _recv_exact(self, n: int) -> Optional[bytes]:
        """Recebe exatamente n bytes."""
        chunks, total = [], 0
        while total < n:
            chunk = self._sock.recv(min(n - total, 4096))
            if not chunk:
                return None
            chunks.append(chunk)
            total += len(chunk)
        return b"".join(chunks)

# ═══════════════════════════════════════════════════════════
# PEER MANAGER
# ═══════════════════════════════════════════════════════════

class PeerManager:
    """
    Gerencia conexões com peers da rede.

    Funcionalidades:
      • Descoberta de peers (bootstrapping + troca entre nós)
      • Conexões persistentes com reconexão automática
      • Rate limiting e banimento de peers maliciosos
      • Propagação de blocos e transações
    """

    BOOTSTRAP_PEERS = [
        ("192.168.0.100", DEFAULT_PORT),
        ("192.168.0.102", DEFAULT_PORT),
        ("192.168.0.103", DEFAULT_PORT),
    ]

    def __init__(self, my_port: int = DEFAULT_PORT):
        self._peers:    dict[str, Peer]  = {}   # addr → Peer
        self._banned:   dict[str, float] = {}   # ip → ban_until
        self._rate:     dict[str, deque] = defaultdict(lambda: deque(maxlen=200))
        self._lock      = threading.RLock()
        self._my_port   = my_port

        # Callbacks registrados por módulos externos
        self._handlers: dict[str, list[Callable]] = defaultdict(list)

        self._load_peers()

    # ── Peers ─────────────────────────────────────────────

    def known_peers(self) -> list[Peer]:
        with self._lock:
            return list(self._peers.values())

    def connected_peers(self) -> list[Peer]:
        with self._lock:
            return [p for p in self._peers.values() if p.connected]

    def add_peer(self, ip: str, port: int = DEFAULT_PORT) -> None:
        key = f"{ip}:{port}"
        with self._lock:
            if key not in self._peers:
                self._peers[key] = Peer(ip, port)

    def ban_peer(self, ip: str, reason: str = "") -> None:
        log.warning("Banindo peer %s por %ds. Motivo: %s", ip, BAN_DURATION, reason)
        self._banned[ip] = time.time() + BAN_DURATION
        with self._lock:
            for key in list(self._peers.keys()):
                if self._peers[key].ip == ip:
                    self._peers[key].disconnect()

    def is_banned(self, ip: str) -> bool:
        ban_until = self._banned.get(ip, 0)
        if ban_until > time.time():
            return True
        if ip in self._banned:
            del self._banned[ip]
        return False

    def peer_count(self) -> int:
        return len(self.connected_peers())

    # ── Rate limiting ─────────────────────────────────────

    def check_rate(self, ip: str) -> bool:
        """Retorna False se o peer excedeu o rate limit."""
        now    = time.time()
        times  = self._rate[ip]
        times.append(now)
        recent = sum(1 for t in times if now - t <= RATE_WINDOW)
        if recent > RATE_MAX_MSG:
            self.ban_peer(ip, "rate limit excedido")
            return False
        return True

    # ── Handlers ─────────────────────────────────────────

    def on(self, cmd: str, handler: Callable = None):
        """Registra um handler. Pode ser usado como decorator ou chamada direta."""
        def decorator(fn):
            self._handlers[cmd].append(fn)
            return fn
        if handler is not None:
            self._handlers[cmd].append(handler)
            return handler
        return decorator

    def _dispatch(self, peer: Peer, cmd: str, payload: dict) -> None:
        for handler in self._handlers.get(cmd, []):
            try:
                handler(peer, payload)
            except Exception as e:
                log.error("Handler de %s falhou: %s", cmd, e)

    # ── Conexão e escuta ──────────────────────────────────

    def start(self) -> None:
        """Inicia servidor TCP e threads de gerenciamento."""
        threading.Thread(target=self._server_loop, daemon=True, name="net.server").start()
        threading.Thread(target=self._connect_loop, daemon=True, name="net.connect").start()
        threading.Thread(target=self._ping_loop, daemon=True, name="net.ping").start()
        log.info("Servidor P2P iniciado na porta %d", self._my_port)

    def _server_loop(self) -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        srv.bind(("0.0.0.0", self._my_port))
        srv.listen(32)

        while True:
            try:
                conn, addr = srv.accept()
                ip = addr[0]
                if self.is_banned(ip):
                    conn.close()
                    continue
                conn.settimeout(30)
                key  = f"{ip}:{addr[1]}"
                peer = self._peers.get(key)
                if peer is None:
                    peer = Peer(ip, addr[1])
                    peer._sock     = conn
                    peer.connected = True
                    with self._lock:
                        self._peers[key] = peer
                else:
                    peer._sock     = conn
                    peer.connected = True
                threading.Thread(
                    target=self._peer_loop,
                    args=(peer,),
                    daemon=True,
                    name=f"net.peer.{ip}",
                ).start()
            except Exception as e:
                log.error("Erro no servidor: %s", e)

    def _peer_loop(self, peer: Peer) -> None:
        """Loop de leitura de mensagens de um peer."""
        self._send_version(peer)

        while peer.connected:
            msg = peer.recv_message()
            if msg is None:
                break
            cmd, payload = msg

            if not self.check_rate(peer.ip):
                break

            self._dispatch(peer, cmd, payload)

        peer.disconnect()
        log.debug("Peer %s desconectado.", peer.addr)

    def _connect_loop(self) -> None:
        """Tenta conectar a peers conhecidos periodicamente."""
        # Bootstrap inicial
        for ip, port in self.BOOTSTRAP_PEERS:
            self.add_peer(ip, port)

        while True:
            with self._lock:
                candidates = [
                    p for p in self._peers.values()
                    if not p.connected and not self.is_banned(p.ip)
                ]

            connected = self.peer_count()
            slots     = MAX_PEERS - connected

            for peer in random.sample(candidates, min(len(candidates), max(0, slots))):
                if peer.connect():
                    threading.Thread(
                        target=self._peer_loop,
                        args=(peer,),
                        daemon=True,
                        name=f"net.peer.{peer.ip}",
                    ).start()

            self._save_peers()
            time.sleep(30)

    def _ping_loop(self) -> None:
        """Envia PING a todos os peers conectados a cada 60s."""
        while True:
            time.sleep(60)
            nonce = random.randint(0, 2**32)
            for peer in self.connected_peers():
                peer.send(MSG_PING, {"nonce": nonce})

            # Remove peers inativos (sem resposta por > 10 min)
            cutoff = time.time() - 600
            for peer in list(self.connected_peers()):
                if peer.last_seen < cutoff:
                    log.info("Peer %s inativo — desconectando.", peer.addr)
                    peer.disconnect()

    # ── Handshake ─────────────────────────────────────────

    def _send_version(self, peer: Peer) -> None:
        peer.send(MSG_VERSION, {
            "version":   PROTOCOL_VERSION,
            "port":      self._my_port,
            "timestamp": time.time(),
        })

    # ── Broadcast ─────────────────────────────────────────

    def broadcast_block(self, block: dict) -> int:
        """Propaga um bloco para todos os peers conectados. Retorna contagem."""
        sent = 0
        for peer in self.connected_peers():
            if peer.send(MSG_BLOCK, {"block": block}):
                sent += 1
        return sent

    def broadcast_tx(self, tx: dict) -> int:
        sent = 0
        for peer in self.connected_peers():
            if peer.send(MSG_TX, {"tx": tx}):
                sent += 1
        return sent

    def request_blocks_from(self, peer: Peer, known_hashes: list[str]) -> None:
        peer.send(MSG_GETBLOCKS, {"known": known_hashes[-10:]})

    # ── Persistência de peers ─────────────────────────────

    def _save_peers(self) -> None:
        data = [
            {"ip": p.ip, "port": p.port, "last_seen": p.last_seen}
            for p in self._peers.values()
            if not self.is_banned(p.ip)
        ]
        tmp = PEERS_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, PEERS_FILE)

    def _load_peers(self) -> None:
        if not os.path.exists(PEERS_FILE):
            return
        try:
            with open(PEERS_FILE) as f:
                data = json.load(f)
            for entry in data:
                self.add_peer(entry["ip"], entry.get("port", DEFAULT_PORT))
        except Exception as e:
            log.warning("Erro ao carregar peers: %s", e)
