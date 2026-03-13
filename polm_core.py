"""
polm_core.py — PoLM Blockchain Core
=====================================
Constantes, estruturas de dados, hashing, validação, genesis block.
Importado por todos os outros módulos.
"""

import hashlib
import json
import os
import time
from typing import Optional

# ═══════════════════════════════════════════════════════════
# CONSTANTES IMUTÁVEIS DA REDE
# ═══════════════════════════════════════════════════════════

NETWORK_VERSION   = 1
NETWORK_MAGIC     = 0xD9B4BEF9          # 4 bytes de identificação da rede
COIN              = 100_000_000         # 1 PoLM = 100.000.000 satoshis (8 casas)
MAX_SUPPLY_COINS  = 32_000_000          # 32 milhões de PoLM
MAX_SUPPLY_SATS   = MAX_SUPPLY_COINS * COIN

# Recompensa inicial e halving (como Bitcoin)
INITIAL_REWARD_SATS = 50 * COIN         # 50 PoLM no bloco 0
HALVING_INTERVAL    = 210_000           # a cada 210.000 blocos, recompensa cai pela metade

# Tempo alvo entre blocos
TARGET_BLOCK_TIME   = 60                # segundos
DIFFICULTY_WINDOW   = 144              # blocos para recalcular dificuldade (~1 dia)
MIN_DIFFICULTY      = 8
MAX_DIFFICULTY      = 64               # bits de dificuldade (256-bit hash)
INITIAL_DIFFICULTY  = 16

# Limites de bloco
MAX_BLOCK_SIZE      = 1_000_000        # 1 MB
MAX_TX_PER_BLOCK    = 4_000
MAX_MEMPOOL_SIZE    = 50_000
COINBASE_MATURITY   = 100              # blocos para maturar recompensa de mineração

# Rede
DEFAULT_PORT        = 5555
MAX_PEERS           = 125
PROTOCOL_VERSION    = "PoLM/1.0"

# Arquivo de dados
CHAIN_FILE          = "polm_chain.db"
UTXO_FILE           = "polm_utxo.db"
PEERS_FILE          = "polm_peers.json"
WALLET_FILE         = "polm_wallet.json"

# ═══════════════════════════════════════════════════════════
# HASHING
# ═══════════════════════════════════════════════════════════

def sha256d(data: bytes) -> bytes:
    """Hash duplo SHA-256 (igual ao Bitcoin)."""
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def sha256d_hex(data: bytes) -> str:
    return sha256d(data).hex()


def hash_block_header(header: dict) -> str:
    """
    Hash determinístico do cabeçalho do bloco.
    Campos cobertos: version, prev_hash, merkle_root,
                     timestamp, difficulty, nonce, ram_proof
    """
    fields = (
        header["version"],
        header["prev_hash"],
        header["merkle_root"],
        header["timestamp"],
        header["difficulty"],
        header["nonce"],
        header.get("ram_proof", ""),
    )
    raw = "|".join(str(f) for f in fields).encode()
    return sha256d_hex(raw)


def hash_transaction(tx: dict) -> str:
    """Hash de uma transação (todos os campos exceto 'txid')."""
    clean = {k: v for k, v in tx.items() if k != "txid"}
    raw   = json.dumps(clean, sort_keys=True, separators=(",", ":")).encode()
    return sha256d_hex(raw)


def merkle_root(txids: list[str]) -> str:
    """Calcula a raiz da Merkle Tree de uma lista de txids (hex de 64 chars)."""
    if not txids:
        return "0" * 64

    def _ensure_hex64(s: str) -> str:
        if len(s) == 64:
            try:
                int(s, 16)
                return s
            except ValueError:
                pass
        return hashlib.sha256(s.encode()).hexdigest()

    layer = [_ensure_hex64(t) for t in txids]

    while len(layer) > 1:
        if len(layer) % 2:
            layer.append(layer[-1])
        layer = [
            sha256d_hex(bytes.fromhex(layer[i]) + bytes.fromhex(layer[i+1]))
            for i in range(0, len(layer), 2)
        ]
    return layer[0]

# ═══════════════════════════════════════════════════════════
# RECOMPENSA DE MINERAÇÃO (Halving como Bitcoin)
# ═══════════════════════════════════════════════════════════

def block_reward_sats(height: int) -> int:
    """
    Calcula a recompensa em satoshis para um bloco de altura `height`.
    A recompensa cai pela metade a cada HALVING_INTERVAL blocos.
    Após ~22 halvings a recompensa é 0 (supply esgotado).
    """
    halvings = height // HALVING_INTERVAL
    if halvings >= 64:
        return 0
    reward = INITIAL_REWARD_SATS >> halvings
    return reward

# ═══════════════════════════════════════════════════════════
# DIFICULDADE
# ═══════════════════════════════════════════════════════════

def bits_to_target(bits: int) -> int:
    """Converte bits de dificuldade em target numérico."""
    return 2 ** (256 - bits)


def hash_meets_target(h: str, bits: int) -> bool:
    """Verifica se o hash satisfaz a dificuldade atual."""
    return int(h, 16) < bits_to_target(bits)


def calculate_next_difficulty(last_blocks: list[dict]) -> int:
    """
    Retarget de dificuldade (janela deslizante).
    Analisa os últimos DIFFICULTY_WINDOW blocos e ajusta para
    manter o tempo médio próximo de TARGET_BLOCK_TIME.
    """
    if len(last_blocks) < 2:
        return INITIAL_DIFFICULTY

    window   = last_blocks[-min(DIFFICULTY_WINDOW, len(last_blocks)):]
    elapsed  = window[-1]["timestamp"] - window[0]["timestamp"]
    expected = TARGET_BLOCK_TIME * (len(window) - 1)

    if elapsed <= 0 or expected <= 0:
        return INITIAL_DIFFICULTY

    current_diff = window[-1].get("difficulty", INITIAL_DIFFICULTY)
    ratio        = elapsed / expected

    # Anti-oscillação: muda no máximo 4x por janela (como Bitcoin)
    ratio = max(0.25, min(4.0, ratio))

    import math
    new_diff = current_diff - math.log2(ratio)
    new_diff = max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, round(new_diff)))
    return int(new_diff)

# ═══════════════════════════════════════════════════════════
# VALIDAÇÃO DE TRANSAÇÃO
# ═══════════════════════════════════════════════════════════

def validate_tx_structure(tx: dict) -> tuple[bool, str]:
    """Validação estrutural de uma transação (sem verificar UTXOs)."""

    if not isinstance(tx, dict):
        return False, "tx não é um objeto"

    required = {"version", "inputs", "outputs", "locktime"}
    missing  = required - tx.keys()
    if missing:
        return False, f"campos faltando: {missing}"

    if not isinstance(tx["inputs"], list) or not tx["inputs"]:
        return False, "inputs inválidos"

    if not isinstance(tx["outputs"], list) or not tx["outputs"]:
        return False, "outputs inválidos"

    for i, inp in enumerate(tx["inputs"]):
        if not isinstance(inp, dict):
            return False, f"input {i} inválido"
        if "txid" not in inp or "vout" not in inp:
            # Coinbase tem txid "0"*64 e vout -1
            if inp.get("txid") != "0" * 64:
                return False, f"input {i} sem txid/vout"

    for i, out in enumerate(tx["outputs"]):
        if not isinstance(out, dict):
            return False, f"output {i} inválido"
        if "value" not in out or "address" not in out:
            return False, f"output {i} sem value/address"
        if not isinstance(out["value"], int) or out["value"] < 0:
            return False, f"output {i} com value inválido"
        if not isinstance(out["address"], str) or len(out["address"]) < 20:
            return False, f"output {i} com address inválido"

    total_out = sum(o["value"] for o in tx["outputs"])
    if total_out > MAX_SUPPLY_SATS:
        return False, "outputs excedem supply máximo"

    return True, "ok"

# ═══════════════════════════════════════════════════════════
# VALIDAÇÃO DE BLOCO
# ═══════════════════════════════════════════════════════════

def validate_block_structure(block: dict) -> tuple[bool, str]:
    """Valida a estrutura e consistência de um bloco."""

    required = {
        "version", "height", "prev_hash", "merkle_root",
        "timestamp", "difficulty", "nonce", "hash",
        "miner", "transactions", "ram_proof", "ram_score",
    }
    missing = required - block.keys()
    if missing:
        return False, f"campos faltando: {missing}"

    # Hash do bloco
    computed = hash_block_header(block)
    if computed != block["hash"]:
        return False, f"hash inválido: {computed[:8]}… ≠ {block['hash'][:8]}…"

    # PoW
    if not hash_meets_target(block["hash"], block["difficulty"]):
        return False, f"hash não atende dificuldade {block['difficulty']}"

    # Merkle root
    txids = [tx.get("txid", hash_transaction(tx)) for tx in block["transactions"]]
    computed_mr = merkle_root(txids)
    if computed_mr != block["merkle_root"]:
        return False, "merkle_root inválido"

    # Número de transações
    if len(block["transactions"]) > MAX_TX_PER_BLOCK:
        return False, "excesso de transações"

    # Primeira transação deve ser coinbase
    if not block["transactions"]:
        return False, "bloco sem transações"

    coinbase = block["transactions"][0]
    if not _is_coinbase(coinbase):
        return False, "primeira tx não é coinbase"

    # Valida estrutura de cada transação
    for i, tx in enumerate(block["transactions"]):
        ok, reason = validate_tx_structure(tx)
        if not ok:
            return False, f"tx {i}: {reason}"

    # Timestamp não pode ser muito no futuro (2 horas)
    if block["timestamp"] > time.time() + 7200:
        return False, "timestamp no futuro"

    return True, "ok"


def _is_coinbase(tx: dict) -> bool:
    """Verifica se uma transação é coinbase."""
    inputs = tx.get("inputs", [])
    return (
        len(inputs) == 1
        and inputs[0].get("txid") == "0" * 64
        and inputs[0].get("vout") == -1
    )

# ═══════════════════════════════════════════════════════════
# GENESIS BLOCK
# ═══════════════════════════════════════════════════════════

def create_genesis_block() -> dict:
    """
    Cria o bloco gênesis do PoLM.
    Inclui uma mensagem imutável na coinbase (como Satoshi fez).
    """
    genesis_message = (
        "PoLM 2025 — Aluisio Fernandes 'Aluminium' — "
        "Hardware antigo nao morre, ele minera. "
        "DDR2 tem valor. Cada ciclo de RAM e prova de vida."
    )

    coinbase_tx = {
        "version": 1,
        "inputs": [{
            "txid":       "0" * 64,
            "vout":       -1,
            "coinbase":   genesis_message.encode().hex(),
            "sequence":   0xFFFFFFFF,
        }],
        "outputs": [{
            "value":   INITIAL_REWARD_SATS,
            "address": "PoLM1Genesis0000000000000000000000000000000",
        }],
        "locktime": 0,
    }
    coinbase_tx["txid"] = hash_transaction(coinbase_tx)

    genesis = {
        "version":      NETWORK_VERSION,
        "height":       0,
        "prev_hash":    "0" * 64,
        "timestamp":    1_700_000_000,
        "difficulty":   INITIAL_DIFFICULTY,
        "nonce":        0,
        "miner":        "PoLM-Genesis",
        "transactions": [coinbase_tx],
        "ram_proof":    "genesis",
        "ram_score":    0.0,
    }

    txids             = [coinbase_tx["txid"]]
    genesis["merkle_root"] = merkle_root(txids)
    genesis["hash"]   = "00000000" + "0" * 56   # hash simbólico do genesis

    return genesis
