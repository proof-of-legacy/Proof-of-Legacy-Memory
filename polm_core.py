"""
polm_core.py — PoLM Blockchain Core v1.2
==========================================
CHANGELOG v1.2:
  - Sistema de ÉPOCAS: RAM mínima aumenta progressivamente
  - DDR2 obsoleto na época 4 (como ASICs ficam obsoletos no Bitcoin)
  - Multiplicadores rebalanceados para DDR2 dominar nas primeiras épocas
  - Dificuldade efetiva reduzida pelo score de RAM (hardware legacy minera mais)
  - RAM mínima por época: 256MB → 512MB → 1GB → 2GB → 4GB → 8GB...
  - Chain ID para anti-replay attack
  - MAX_REORG_DEPTH para segurança
"""

import hashlib
import json
import math
import os
import time
from typing import Optional

# ═══════════════════════════════════════════════════════════
# CONSTANTES IMUTÁVEIS DA REDE
# ═══════════════════════════════════════════════════════════

NETWORK_VERSION     = 1
NETWORK_MAGIC       = 0xD9B4BEF9
CHAIN_ID            = "polm-mainnet-1"
COIN                = 100_000_000
MAX_SUPPLY_COINS    = 32_000_000
MAX_SUPPLY_SATS     = MAX_SUPPLY_COINS * COIN

INITIAL_REWARD_SATS = 50 * COIN
HALVING_INTERVAL    = 210_000

TARGET_BLOCK_TIME   = 150   # 2.5 min — época 4 em ~4 anos
DIFFICULTY_WINDOW   = 144   # ~6 horas de janela
MIN_DIFFICULTY      = 10
MAX_DIFFICULTY      = 22
INITIAL_DIFFICULTY  = 14

MAX_BLOCK_SIZE      = 1_000_000
MAX_TX_PER_BLOCK    = 4_000
MAX_MEMPOOL_SIZE    = 50_000
COINBASE_MATURITY   = 100
MAX_REORG_DEPTH     = 100
MAX_PEERS_FROM_MSG  = 50

DEFAULT_PORT        = 5555
MAX_PEERS           = 125
PROTOCOL_VERSION    = "PoLM/1.2"

CHAIN_FILE          = "polm_chain.db"
UTXO_FILE           = "polm_utxo.db"
PEERS_FILE          = "polm_peers.json"
WALLET_FILE         = "polm_wallet.json"

# ═══════════════════════════════════════════════════════════
# SISTEMA DE PENALIZAÇÃO DE CPU
# ═══════════════════════════════════════════════════════════
#
# Hardware mais antigo e menos cores = mais poder de mineração
# Um Core 2 Duo 2006 DDR2 deve dominar sobre um i9 DDR5
#
# Detecção: número de cores físicos do sistema
# Quanto menos cores = mais antigo = mais mult CPU
#
# MULTIPLICADORES DE CPU:
# 1-2 cores  → mult 3.0x  (Athlon XP, Pentium 4, Athlon 64 X2, Core 2 Duo ~2001-2008)
# 3-4 cores  → mult 2.0x  (Core i3/i5 1ª geração, Phenom II ~2008-2012)
# 5-8 cores  → mult 1.0x  (Core i5/i7 médio, Ryzen 5 ~2014-2019) ← baseline
# 9-16 cores → mult 0.5x  (Core i7/i9, Ryzen 7/9 ~2020+)
# 17+ cores  → mult 0.2x  (Xeon, Threadripper — muito penalizado)
#
# Score final = RAM_score × RAM_mult × CPU_mult
# Athlon 64 X2 + DDR2: score ~140 × 4.0 × 3.0 = 1680 → domina
# i9 + DDR5:           score ~30  × 0.4 × 0.2 = 2.4  → penalizado

CPU_MULTIPLIERS = [
    (2,  3.0),   # 1-2 cores: Pentium, Core 2 Duo — DOMINA
    (4,  2.0),   # 3-4 cores: Core i3/i5 antigo
    (8,  1.0),   # 5-8 cores: Core i5/i7 médio — baseline
    (16, 0.5),   # 9-16 cores: Core i7/i9 novo
    (999, 0.2),  # 17+ cores: Xeon/Threadripper — penalizado
]

def get_cpu_multiplier(num_cores: int, height: int = 0) -> tuple:
    """
    Retorna (multiplier, allowed) baseado no número de cores e época.
    Assim como RAM, CPUs mais antigas ficam obsoletas com o tempo.
    """
    cfg = get_epoch_config(height)
    cpu_rules = cfg.get("_cpu", CPU_MULTIPLIERS)

    for max_cores, mult in cpu_rules:
        if num_cores <= max_cores:
            if mult is None:
                return 0.0, False
            return mult, True
    return 0.1, True

def detect_cpu_cores() -> int:
    """Detecta número de cores físicos (não lógicos/HT)."""
    import os
    try:
        # Linux: cores físicos via /sys
        import subprocess
        out = subprocess.check_output(
            ["grep", "-c", "^processor", "/proc/cpuinfo"],
            stderr=subprocess.DEVNULL, timeout=3
        ).decode().strip()
        logical = int(out)

        # Tenta detectar cores físicos
        try:
            out2 = subprocess.check_output(
                ["grep", "cpu cores", "/proc/cpuinfo"],
                stderr=subprocess.DEVNULL, timeout=3
            ).decode()
            cores_per_socket = int(out2.split(":")[-1].strip().split("\n")[0])
            sockets = max(1, logical // (cores_per_socket * 2))
            physical = cores_per_socket * sockets
            return physical
        except Exception:
            # Fallback: usa lógicos / 2 (assume HT)
            return max(1, logical // 2)
    except Exception:
        return os.cpu_count() or 2

# ═══════════════════════════════════════════════════════════
# SISTEMA DE ÉPOCAS — O CORAÇÃO DO PoLM
# ═══════════════════════════════════════════════════════════
#
# Assim como Bitcoin exige cada vez mais energia (hashrate),
# PoLM exige cada vez mais RAM. Isso incentiva:
#   1. Uso de hardware legacy (DDR2/DDR3) nas épocas iniciais
#   2. Com o tempo, DDR2 fica obsoleto (máx 4GB disponível)
#   3. Mineradores precisam adicionar mais módulos DDR3/DDR4/DDR5
#   4. Placas mãe dedicadas com muitos slots serão vantajosas
#
# ÉPOCAS (a cada 210.000 blocos — ~400 dias):
#
# Época 0 (blocos 0-209.999):
#   RAM mínima: 256 MB
#   DDR2 permitido: SIM (mult=4.0x) ← DOMINA
#   DDR3 permitido: SIM (mult=2.5x)
#   DDR4 permitido: SIM (mult=1.0x)
#   DDR5 permitido: SIM (mult=0.4x)
#
# Época 1 (blocos 210.000-419.999):
#   RAM mínima: 512 MB
#   DDR2 permitido: SIM (mult=3.5x) ← ainda forte
#   DDR3 permitido: SIM (mult=2.5x)
#   DDR4 permitido: SIM (mult=1.0x)
#   DDR5 permitido: SIM (mult=0.4x)
#
# Época 2 (blocos 420.000-629.999):
#   RAM mínima: 1 GB
#   DDR2 permitido: SIM (mult=3.0x) ← enfraquecendo
#   DDR3 permitido: SIM (mult=2.5x)
#   DDR4 permitido: SIM (mult=1.0x)
#   DDR5 permitido: SIM (mult=0.4x)
#
# Época 3 (blocos 630.000-839.999):
#   RAM mínima: 2 GB
#   DDR2 permitido: SIM (mult=2.0x) ← difícil (máx ~4GB DDR2 existe)
#   DDR3 permitido: SIM (mult=2.5x) ← DDR3 domina
#   DDR4 permitido: SIM (mult=1.0x)
#   DDR5 permitido: SIM (mult=0.4x)
#
# Época 4 (blocos 840.000-1.049.999):
#   RAM mínima: 4 GB
#   DDR2 permitido: NÃO ← OBSOLETO (não existe DDR2 de 4GB+)
#   DDR3 permitido: SIM (mult=2.5x) ← DOMINA
#   DDR4 permitido: SIM (mult=1.0x)
#   DDR5 permitido: SIM (mult=0.4x)
#
# Época 5 (blocos 1.050.000+):
#   RAM mínima: 8 GB
#   DDR2 permitido: NÃO
#   DDR3 permitido: SIM (mult=2.0x) ← enfraquecendo
#   DDR4 permitido: SIM (mult=1.2x) ← favorecido
#   DDR5 permitido: SIM (mult=0.5x)
#
# Época 6+: RAM mínima dobra a cada época
#   DDR3 obsoleto na época 6 (máx ~16GB DDR3 disponível)
#   DDR4 domina nas épocas 6-8
#   DDR5 domina na época 9+

EPOCH_INTERVAL = 210_000  # blocos por época (igual ao halving)

# Configuração de cada época: {epoch: {ram_type: multiplier}}
# None = proibido nessa época
# =============================================================
# ÉPOCAS PoLM — DDR2 NUNCA FICA OBSOLETO
# =============================================================
# A visão do fundador: forçar criação de hardware dedicado.
# Quem quiser minerar com DDR2 nas épocas avançadas precisará
# de placas mãe com muitos slots — como ASICs do Bitcoin.
# DDR2 de 2GB por slot: precisa de 1 slot na época 0,
# 2 slots na época 1, 4 slots na época 2... etc.
# Isso cria um mercado para DDR2 que nunca existiu!
#
# Época 0: 2 GB mínimo  → 1x stick DDR2 2GB
# Época 1: 4 GB mínimo  → 2x sticks DDR2 2GB
# Época 2: 8 GB mínimo  → 4x sticks DDR2 2GB
# Época 3: 16 GB mínimo → 8x sticks DDR2 2GB (placa dedicada!)
# Época 4: 32 GB mínimo → 16x sticks DDR2 2GB (ASIC da RAM!)
# Época 5: 64 GB mínimo → 32x sticks DDR2 2GB
# ...
# DDR3 sempre preferido (mult maior) mas DDR2 sempre aceito
EPOCH_CONFIG = {
    # ══════════════════════════════════════════════════════════════════
    # SISTEMA DE ÉPOCAS PoLM — ESCALADA AGRESSIVA DE RAM
    # ══════════════════════════════════════════════════════════════════
    #
    # Quanto mais valioso o projeto = mais RAM necessária
    # Como Bitcoin: preço alto → mais hashrate → mais dificuldade
    # PoLM: preço alto → mais RAM → mais sticks → hardware dedicado
    #
    # RAM mínima dobra a cada época (~1 ano)
    # A cada 2 épocas: geração mais antiga SAI, próxima DOMINA
    #
    # Sticks por geração (tamanho máx por stick):
    # DDR1  → 1 GB/stick
    # DDR2  → 2 GB/stick
    # DDR3  → 8 GB/stick
    # DDR4  → 32 GB/stick
    # DDR5  → 64 GB/stick
    #
    # ESCALA DE INVESTIMENTO EM RAM:
    # Época 0: ~$5    (2GB DDR2)
    # Época 1: ~$10   (4GB DDR2)
    # Época 2: ~$40   (8x sticks DDR2 2GB = 16GB)  ← placa dedicada
    # Época 3: ~$80   (8x sticks DDR2 2GB = 16GB)
    # Época 4: ~$200  (8x sticks DDR3 8GB = 64GB)  ← ASIC DDR3
    # Época 5: ~$500  (16x sticks DDR3 8GB = 128GB)
    # Época 6: ~$2000 (8x sticks DDR4 32GB = 256GB) ← ASIC DDR4
    # Época 7: ~$5000 (16x sticks DDR4 32GB = 512GB)
    # Época 8: ~$20k  (8x sticks DDR5 64GB = 512GB) ← ASIC DDR5
    # Época 9: ~$50k  (16x sticks DDR5 64GB = 1TB)
    # Época 10+: investimento industrial
    # ══════════════════════════════════════════════════════════════════

    # ── ÉPOCA 0: DDR1 domina | 2 GB mínimo ───────────────────────
    0: {
        "min_ram_mb":  2048,
        "DDR1":  6.0,   "DDR2":  4.0,   "DDR3":  2.0,
        "DDR4":  0.8,   "DDR5":  0.3,
        "LPDDR3": 1.5,  "LPDDR4": 0.7,  "LPDDR5": 0.25,
        "AUTO":  0.8,
        "_cpu": [(1,4.0),(2,4.0),(4,2.5),(8,1.0),(16,0.4),(999,0.1)],
        "_min_ram_by_type": {"DDR1":2048,"DDR2":2048,"DDR3":2048,"DDR4":2048,"DDR5":2048},
    },
    # ── ÉPOCA 1: DDR1 cai | DDR2 sobe | 4 GB mínimo ──────────────
    1: {
        "min_ram_mb":  4096,
        "DDR1":  5.5,   "DDR2":  4.0,   "DDR3":  2.2,
        "DDR4":  0.9,   "DDR5":  0.35,
        "LPDDR3": 1.8,  "LPDDR4": 0.8,  "LPDDR5": 0.3,
        "AUTO":  0.9,
        "_cpu": [(1,3.5),(2,3.5),(4,2.5),(8,1.0),(16,0.4),(999,0.1)],
        "_min_ram_by_type": {"DDR1":4096,"DDR2":4096,"DDR3":4096,"DDR4":4096,"DDR5":4096},
    },
    # ── ÉPOCA 2: DDR1 SAI | DDR2 DOMINA | 8 GB mínimo ────────────
    # DDR2: 4x sticks 2GB — primeiro hardware dedicado!
    2: {
        "min_ram_mb":  8192,
        "DDR1":  None,  "DDR2":  6.0,   "DDR3":  3.0,
        "DDR4":  1.0,   "DDR5":  0.4,
        "LPDDR3": 2.5,  "LPDDR4": 0.9,  "LPDDR5": 0.35,
        "AUTO":  1.0,
        "_cpu": [(1,None),(2,4.0),(4,3.0),(8,2.0),(16,0.8),(999,0.2)],
        "_min_ram_by_type": {"DDR2":8192,"DDR3":8192,"DDR4":8192,"DDR5":8192},
    },
    # ── ÉPOCA 3: DDR2 domina | 16 GB mínimo ──────────────────────
    # DDR2: 8x sticks 2GB — placa dedicada necessária!
    3: {
        "min_ram_mb":  16384,
        "DDR1":  None,  "DDR2":  5.5,   "DDR3":  3.5,
        "DDR4":  1.2,   "DDR5":  0.45,
        "LPDDR3": 3.0,  "LPDDR4": 1.0,  "LPDDR5": 0.4,
        "AUTO":  1.0,
        "_cpu": [(1,None),(2,3.5),(4,3.0),(8,2.0),(16,0.8),(999,0.2)],
        "_min_ram_by_type": {"DDR2":16384,"DDR3":16384,"DDR4":16384,"DDR5":16384},
    },
    # ── ÉPOCA 4: DDR2 SAI | DDR3 DOMINA | 32 GB mínimo ──────────
    # DDR3: 4x sticks 8GB | DDR4: 1x stick 32GB
    4: {
        "min_ram_mb":  32768,
        "DDR1":  None,  "DDR2":  None,  "DDR3":  6.0,
        "DDR4":  2.0,   "DDR5":  0.8,
        "LPDDR3": 4.0,  "LPDDR4": 1.8,  "LPDDR5": 0.7,
        "AUTO":  1.5,
        "_cpu": [(1,None),(2,None),(4,4.0),(8,2.5),(16,1.2),(999,0.5)],
        "_min_ram_by_type": {"DDR3":32768,"DDR4":32768,"DDR5":32768},
    },
    # ── ÉPOCA 5: DDR3 domina | 64 GB mínimo ──────────────────────
    # DDR3: 8x sticks 8GB — ASIC DDR3!
    5: {
        "min_ram_mb":  65536,
        "DDR1":  None,  "DDR2":  None,  "DDR3":  5.5,
        "DDR4":  2.5,   "DDR5":  1.0,
        "LPDDR3": 3.5,  "LPDDR4": 2.2,  "LPDDR5": 0.9,
        "AUTO":  1.5,
        "_cpu": [(1,None),(2,None),(4,3.5),(8,2.5),(16,1.2),(999,0.5)],
        "_min_ram_by_type": {"DDR3":65536,"DDR4":65536,"DDR5":65536},
    },
    # ── ÉPOCA 6: DDR3 SAI | DDR4 DOMINA | 128 GB mínimo ─────────
    # DDR4: 4x sticks 32GB — investimento ~$2000
    6: {
        "min_ram_mb":  131072,
        "DDR1":  None,  "DDR2":  None,  "DDR3":  None,
        "DDR4":  6.0,   "DDR5":  2.0,
        "LPDDR3": None, "LPDDR4": 4.0,  "LPDDR5": 1.8,
        "AUTO":  2.0,
        "_cpu": [(1,None),(2,None),(4,None),(8,4.0),(16,3.0),(999,1.5)],
        "_min_ram_by_type": {"DDR4":131072,"DDR5":131072},
    },
    # ── ÉPOCA 7: DDR4 domina | 256 GB mínimo ─────────────────────
    # DDR4: 8x sticks 32GB — ASIC DDR4! investimento ~$5000
    7: {
        "min_ram_mb":  262144,
        "DDR1":  None,  "DDR2":  None,  "DDR3":  None,
        "DDR4":  5.5,   "DDR5":  2.5,
        "LPDDR3": None, "LPDDR4": 3.5,  "LPDDR5": 2.2,
        "AUTO":  2.0,
        "_cpu": [(1,None),(2,None),(4,None),(8,3.5),(16,3.0),(999,1.5)],
        "_min_ram_by_type": {"DDR4":262144,"DDR5":262144},
    },
    # ── ÉPOCA 8: DDR4 SAI | DDR5 DOMINA | 512 GB mínimo ─────────
    # DDR5: 8x sticks 64GB — investimento ~$20.000
    8: {
        "min_ram_mb":  524288,
        "DDR1":  None,  "DDR2":  None,  "DDR3":  None,
        "DDR4":  None,  "DDR5":  6.0,
        "LPDDR3": None, "LPDDR4": None, "LPDDR5": 4.0,
        "AUTO":  3.0,
        "_cpu": [(1,None),(2,None),(4,None),(8,None),(16,4.0),(999,3.0)],
        "_min_ram_by_type": {"DDR5":524288},
    },
    # ── ÉPOCA 9: DDR5 domina | 1 TB mínimo ───────────────────────
    # DDR5: 16x sticks 64GB — investimento ~$50.000
    9: {
        "min_ram_mb":  1048576,
        "DDR1":  None,  "DDR2":  None,  "DDR3":  None,
        "DDR4":  None,  "DDR5":  5.5,
        "LPDDR3": None, "LPDDR4": None, "LPDDR5": 4.5,
        "AUTO":  3.0,
        "_cpu": [(1,None),(2,None),(4,None),(8,None),(16,3.5),(999,3.0)],
        "_min_ram_by_type": {"DDR5":1048576},
    },
    # ── ÉPOCA 10: 2 TB mínimo | investimento industrial ──────────
    10: {
        "min_ram_mb":  2097152,
        "DDR1":  None,  "DDR2":  None,  "DDR3":  None,
        "DDR4":  None,  "DDR5":  6.0,
        "LPDDR3": None, "LPDDR4": None, "LPDDR5": 5.0,
        "AUTO":  3.5,
        "_cpu": [(1,None),(2,None),(4,None),(8,None),(16,3.0),(999,3.5)],
        "_min_ram_by_type": {"DDR5":2097152},
    },
}

def get_epoch(height: int) -> int:
    """Retorna o número da época para uma altura de bloco."""
    return min(height // EPOCH_INTERVAL, max(EPOCH_CONFIG.keys()))

def get_epoch_config(height: int) -> dict:
    """Retorna a configuração da época para uma altura."""
    epoch = get_epoch(height)
    return EPOCH_CONFIG.get(epoch, EPOCH_CONFIG[max(EPOCH_CONFIG.keys())])

def get_ram_multiplier(ram_type: str, height: int) -> tuple:
    """
    Retorna (multiplier, allowed) para um tipo de RAM em uma altura.
    Se allowed=False, o minerador não pode minerar nessa época.
    """
    cfg  = get_epoch_config(height)
    mult = cfg.get(ram_type.upper())
    if mult is None:
        return 0.0, False
    return mult, True

def get_min_ram_mb(height: int, ram_type: str = None) -> int:
    """
    Retorna a RAM mínima em MB para minerar em uma altura.
    Se ram_type fornecido, retorna o mínimo específico para aquele tipo.
    Ex: DDR2 na época 3 precisa de 16GB (8x sticks 2GB)
    """
    cfg = get_epoch_config(height)
    if ram_type:
        by_type = cfg.get("_min_ram_by_type", {})
        return by_type.get(ram_type.upper(), cfg.get("min_ram_mb", 2048))
    return cfg.get("min_ram_mb", 2048)

def get_epoch_info(height: int) -> dict:
    """Retorna informações completas da época atual."""
    epoch = get_epoch(height)
    cfg   = get_epoch_config(height)
    next_epoch_block = (epoch + 1) * EPOCH_INTERVAL
    blocks_until_next = max(0, next_epoch_block - height)

    skip = {"min_ram_mb", "_cpu", "_min_ram_by_type"}
    allowed = [k for k, v in cfg.items() if k not in skip and v is not None]
    obsolete = [k for k, v in cfg.items() if k not in skip and v is None]

    return {
        "epoch":              epoch,
        "min_ram_mb":         cfg["min_ram_mb"],
        "next_epoch_block":   next_epoch_block,
        "blocks_until_next":  blocks_until_next,
        "allowed_ram":        allowed,
        "obsolete_ram":       obsolete,
    }

# ═══════════════════════════════════════════════════════════
# DIFICULDADE EFETIVA — Score RAM reduz dificuldade
# ═══════════════════════════════════════════════════════════
#
# Um minerador DDR2 com score 200 minera como se a dificuldade
# fosse 4 bits menor que um DDR4 com score 50.
# Fórmula: effective_bits = base_bits - floor(log2(score / 50))

def effective_difficulty(base_bits: int, ram_score: float) -> int:
    """
    Calcula dificuldade efetiva baseada no score de RAM.
    Score alto = dificuldade efetiva menor = mais fácil encontrar bloco.
    """
    if ram_score <= 0:
        return base_bits
    bonus = max(0, int(math.log2(max(ram_score, 1) / 50.0)))
    bonus = min(bonus, 6)  # máx 6 bits de bônus
    return max(MIN_DIFFICULTY, base_bits - bonus)

# ═══════════════════════════════════════════════════════════
# HASHING
# ═══════════════════════════════════════════════════════════

def sha256d(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()

def sha256d_hex(data: bytes) -> str:
    return sha256d(data).hex()

def hash_block_header(header: dict) -> str:
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
    """Hash da transação com CHAIN_ID (anti replay attack)."""
    clean = {k: v for k, v in tx.items() if k not in ("txid", "signatures")}
    clean["_chain_id"] = CHAIN_ID
    raw = json.dumps(clean, sort_keys=True, separators=(",", ":")).encode()
    return sha256d_hex(raw)

def merkle_root(txids: list) -> str:
    if not txids:
        return "0" * 64

    def _ensure_hex64(s):
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
# RECOMPENSA
# ═══════════════════════════════════════════════════════════

def block_reward_sats(height: int) -> int:
    halvings = height // HALVING_INTERVAL
    if halvings >= 64:
        return 0
    return INITIAL_REWARD_SATS >> halvings

# ═══════════════════════════════════════════════════════════
# DIFICULDADE
# ═══════════════════════════════════════════════════════════

def bits_to_target(bits: int) -> int:
    return 2 ** (256 - bits)

def hash_meets_target(h: str, bits: int) -> bool:
    return int(h, 16) < bits_to_target(bits)

def calculate_next_difficulty(last_blocks: list) -> int:
    if len(last_blocks) < 2:
        return INITIAL_DIFFICULTY

    window   = last_blocks[-min(DIFFICULTY_WINDOW, len(last_blocks)):]
    elapsed  = window[-1]["timestamp"] - window[0]["timestamp"]
    expected = TARGET_BLOCK_TIME * (len(window) - 1)

    if elapsed <= 0 or expected <= 0:
        return INITIAL_DIFFICULTY

    current_diff = window[-1].get("difficulty", INITIAL_DIFFICULTY)
    ratio        = elapsed / expected
    ratio        = max(0.5, min(2.0, ratio))

    new_diff = current_diff - math.log2(ratio)
    new_diff = max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, round(new_diff)))
    return int(new_diff)

# ═══════════════════════════════════════════════════════════
# VALIDAÇÃO DE TRANSAÇÃO
# ═══════════════════════════════════════════════════════════

def validate_tx_structure(tx: dict) -> tuple:
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

    is_cb = _is_coinbase(tx)

    if not is_cb:
        sigs = tx.get("signatures", [])
        if not sigs or not isinstance(sigs, list):
            return False, "transação sem assinaturas"
        for sig in sigs:
            if "pubkey" not in sig or "sig" not in sig:
                return False, "assinatura mal formada"

    for i, inp in enumerate(tx["inputs"]):
        if not isinstance(inp, dict):
            return False, f"input {i} inválido"
        if not is_cb:
            if "txid" not in inp or "vout" not in inp:
                return False, f"input {i} sem txid/vout"

    for i, out in enumerate(tx["outputs"]):
        if not isinstance(out, dict):
            return False, f"output {i} inválido"
        if "value" not in out or "address" not in out:
            return False, f"output {i} sem value/address"
        if not isinstance(out["value"], int) or out["value"] <= 0:
            return False, f"output {i} value inválido"
        if not isinstance(out["address"], str) or len(out["address"]) < 20:
            return False, f"output {i} address inválido"

    total_out = sum(o["value"] for o in tx["outputs"])
    if total_out > MAX_SUPPLY_SATS:
        return False, "outputs excedem supply máximo"

    if not isinstance(tx.get("locktime"), int):
        return False, "locktime inválido"

    return True, "ok"

# ═══════════════════════════════════════════════════════════
# VALIDAÇÃO DE BLOCO
# ═══════════════════════════════════════════════════════════

def validate_block_structure(block: dict, prev_block: dict = None) -> tuple:
    required = {
        "version", "height", "prev_hash", "merkle_root",
        "timestamp", "difficulty", "nonce", "hash",
        "miner", "transactions", "ram_proof", "ram_score",
    }
    missing = required - block.keys()
    if missing:
        return False, f"campos faltando: {missing}"

    if block["version"] != NETWORK_VERSION:
        return False, f"versão incompatível: {block['version']}"

    computed = hash_block_header(block)
    if computed != block["hash"]:
        return False, "hash inválido"

    if not hash_meets_target(block["hash"], block["difficulty"]):
        return False, "PoW insuficiente"

    if not (MIN_DIFFICULTY <= block["difficulty"] <= MAX_DIFFICULTY):
        return False, f"dificuldade fora dos limites: {block['difficulty']}"

    if prev_block and block["height"] != prev_block["height"] + 1:
        return False, "altura não sequencial"

    # Valida RAM type para a época atual
    height   = block["height"]
    ram_type = block.get("ram_type", "AUTO")
    _, allowed = get_ram_multiplier(ram_type, height)
    if not allowed and ram_type not in ("genesis", "AUTO"):
        return False, f"RAM {ram_type} obsoleta na época {get_epoch(height)}"

    txids       = [tx.get("txid", hash_transaction(tx)) for tx in block["transactions"]]
    computed_mr = merkle_root(txids)
    if computed_mr != block["merkle_root"]:
        return False, "merkle_root inválido"

    if not block["transactions"]:
        return False, "bloco sem transações"

    if len(block["transactions"]) > MAX_TX_PER_BLOCK:
        return False, "excesso de transações"

    coinbase = block["transactions"][0]
    if not _is_coinbase(coinbase):
        return False, "primeira tx não é coinbase"

    for tx in block["transactions"][1:]:
        if _is_coinbase(tx):
            return False, "múltiplas coinbase no bloco"

    for i, tx in enumerate(block["transactions"]):
        ok, reason = validate_tx_structure(tx)
        if not ok:
            return False, f"tx {i}: {reason}"

    if block["timestamp"] > time.time() + 7200:
        return False, "timestamp no futuro"

    if prev_block and block["timestamp"] < prev_block["timestamp"] - 600:
        return False, "timestamp retroativo"

    if not isinstance(block["miner"], str) or len(block["miner"]) < 20:
        return False, "endereço do minerador inválido"

    return True, "ok"

def _is_coinbase(tx: dict) -> bool:
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
    genesis_message = (
        "PoLM 2025 — Aluisio Fernandes 'Aluminium' — "
        "Hardware antigo nao morre, ele minera. "
        "DDR2 tem valor. Cada ciclo de RAM e prova de vida. "
        "Epoca 0: DDR2 domina. O futuro pertence a quem preserva o passado."
    )

    coinbase_tx = {
        "version": 1,
        "inputs": [{
            "txid":     "0" * 64,
            "vout":     -1,
            "coinbase": genesis_message.encode().hex(),
            "sequence": 0xFFFFFFFF,
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
        "miner":        "PoLM-Genesis-Aluminium",
        "transactions": [coinbase_tx],
        "ram_proof":    "genesis",
        "ram_score":    0.0,
        "ram_type":     "genesis",
        "epoch":        0,
    }

    txids                = [coinbase_tx["txid"]]
    genesis["merkle_root"] = merkle_root(txids)
    genesis["hash"]      = "00000000" + "0" * 56
    return genesis
