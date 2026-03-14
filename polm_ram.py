"""
polm_ram.py — Prova de Latência de RAM Física (PoLM Consensus) v1.2
=====================================================================
PROTEÇÕES ANTI-TRAPAÇA v1.2:
  1. Buffer > cache L3 — garante acesso à RAM física
  2. Multi-round com seeds derivados do block_hash
  3. Variance check — RAM virtual é artificialmente uniforme
  4. Thermal fingerprint — RAM física aquece e fica mais lenta
  5. Page fault detection — RAM física tem page faults reais
  6. Swap detection — penaliza zRAM/swap ativo
  7. Confidence score — penaliza qualquer suspeita de virtualização
"""

import hashlib
import os
import platform
import random
import subprocess
import time
from typing import Optional, Tuple

GRAPH_SIZE    = 100_000   # rounds por prova — RAM latency bound
NUM_ROUNDS    = 3         # rodadas para variance check
MIN_VARIANCE  = 0.02
MAX_VARIANCE  = 0.35
SCORE_MIN     = 0.1
SCORE_MAX     = 200.0
MIN_BUFFER_MB = 256

RAM_MULTIPLIERS = {
    "DDR1": 6.0, "DDR": 6.0,
    "DDR2": 4.0, "DDR3": 2.5,
    "DDR4": 1.0, "DDR5": 0.4,
    "LPDDR3": 2.0, "LPDDR4": 0.9, "LPDDR5": 0.35,
    "AUTO": 1.0,
}

def detect_l3_cache_mb() -> int:
    try:
        for idx in range(10):
            path = f"/sys/devices/system/cpu/cpu0/cache/index{idx}/level"
            if not os.path.exists(path):
                break
            if open(path).read().strip() == "3":
                s = open(f"/sys/devices/system/cpu/cpu0/cache/index{idx}/size").read().strip()
                if s.endswith("K"): return int(s[:-1]) // 1024
                if s.endswith("M"): return int(s[:-1])
    except Exception:
        pass
    return 32

def detect_ram_type() -> Tuple[str, float]:
    ram_type = "AUTO"
    if platform.system() == "Linux":
        try:
            out = subprocess.check_output(
                ["sudo", "dmidecode", "-t", "memory"],
                stderr=subprocess.DEVNULL, timeout=5
            ).decode(errors="ignore")
            for gen in ["DDR5","LPDDR5","LPDDR4","DDR4","LPDDR3","DDR3","DDR2","DDR "]:
                if gen in out:
                    ram_type = gen.strip()
                    if ram_type == "DDR": ram_type = "DDR1"
                    break
        except Exception:
            pass
    elif platform.system() == "Darwin":
        try:
            out = subprocess.check_output(
                ["system_profiler","SPMemoryDataType"],
                stderr=subprocess.DEVNULL, timeout=5
            ).decode(errors="ignore")
            for gen in ["DDR5","DDR4","DDR3","DDR2"]:
                if gen in out:
                    ram_type = gen
                    break
        except Exception:
            pass
    return ram_type, RAM_MULTIPLIERS.get(ram_type, 1.0)

def detect_physical_ram_gb() -> float:
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / 1_048_576
    except Exception:
        pass
    return 0.0

_buffer: Optional[bytearray] = None
_buffer_size: int = 0

def init_buffer(size_mb: int = 256) -> bytearray:
    global _buffer, _buffer_size
    l3_mb   = detect_l3_cache_mb()
    size_mb = max(size_mb, l3_mb * 2, MIN_BUFFER_MB)
    size    = size_mb * 1024 * 1024
    print(f"[PoLM RAM] Alocando {size_mb} MB de buffer (L3={l3_mb}MB)... ", end="", flush=True)
    t0 = time.perf_counter()
    seed_size  = min(size, 4 * 1024 * 1024)
    seed_bytes = os.urandom(seed_size)
    buf   = bytearray(size)
    chunk = len(seed_bytes)
    for offset in range(0, size, chunk):
        end   = min(offset + chunk, size)
        block = seed_bytes if offset == 0 else hashlib.sha256(
            seed_bytes + offset.to_bytes(8, "big")
        ).digest() * (chunk // 32 + 1)
        buf[offset:end] = block[:end - offset]
    # Força alocação física — page touch em todas as páginas
    total = 0
    for i in range(0, size, 4096):
        total ^= buf[i]
    if total == 0: buf[0] = 1
    elapsed = time.perf_counter() - t0
    print(f"OK ({elapsed:.2f}s)")
    _buffer = buf
    _buffer_size = size
    return buf

def get_buffer() -> bytearray:
    global _buffer
    if _buffer is None:
        _buffer = init_buffer(256)
    return _buffer

def memory_storm(seed: int, buf: Optional[bytearray] = None) -> Tuple[int, float]:
    """
    Prova de latência de RAM física — pointer chasing puro.

    Algoritmo RAM-latency-bound:
      1. Hash inicial derivado do seed
      2. A cada iteração: idx = hash % buffer_size
      3. Lê 32 bytes da posição idx (cache miss garantido — buffer > L3)
      4. hash = SHA256(hash + bytes_lidos)
      5. Cada iteração DEPENDE da anterior — impossível paralelizar

    Por que isso mede latência real da RAM?
      • Buffer 256MB+ > qualquer cache L3 (tipicamente 8-32MB)
      • Acesso pseudo-aleatório — impossível pré-buscar (prefetch)
      • Pointer chasing — próximo acesso depende do resultado atual
      • SHA256 é rápido (~5ns) vs RAM (~15-100ns) — RAM é o gargalo

    DDR2 (~100ns latência) vs DDR4 (~15ns):
      → DDR2 naturalmente ~6x mais lento = 6x mais poder PoLM
      → Sem necessidade de multiplicadores artificiais
    """
    if buf is None:
        buf = get_buffer()

    size = len(buf)
    safe = size - 32          # evita leitura fora do buffer
    h    = hashlib.sha256(seed.to_bytes(8, "big")).digest()

    t0 = time.perf_counter()
    for _ in range(GRAPH_SIZE):
        # Índice derivado do hash atual — pointer chasing
        idx = int.from_bytes(h[:8], "big") % safe
        # Lê 32 bytes da RAM física (cache miss garantido)
        val = bytes(buf[idx:idx + 32])
        # Mistura — CPU mínimo, RAM é o gargalo
        h   = hashlib.sha256(h + val).digest()

    checksum = int.from_bytes(h, "big")
    return checksum, time.perf_counter() - t0

def _check_page_fault_pattern(buf: bytearray) -> float:
    """
    Mede ratio primeira/segunda passagem.
    RAM física: primeira passagem mais lenta (page faults reais).
    RAM virtual: ambas iguais (suspeito).
    """
    size = len(buf)
    step = max(4096, size // 1000)
    total = 0
    t0 = time.perf_counter()
    for i in range(0, size, step): total ^= buf[i]
    t1 = time.perf_counter()
    for i in range(0, size, step): total ^= buf[i]
    t2 = time.perf_counter()
    first  = t1 - t0
    second = t2 - t1
    if second < 0.0001: return 1.0
    return first / second

def _check_thermal(buf: bytearray) -> Tuple[float, float]:
    """
    RAM física aquece e fica 5-15% mais lenta.
    RAM virtual mantém latência constante.
    """
    seed  = random.randint(0, 2**32)
    times = []
    for i in range(3):
        _, lat = memory_storm(seed + i, buf)
        times.append(lat)
    return times[0], sum(times[1:]) / 2

def _check_variance(latencies: list) -> float:
    """Coeficiente de variação — RAM física tem CV entre 2-30%."""
    if not latencies: return 0.0
    mean = sum(latencies) / len(latencies)
    if mean == 0: return 0.0
    var = sum((x - mean)**2 for x in latencies) / len(latencies)
    return (var ** 0.5) / mean

def _check_swap() -> Tuple[bool, str]:
    """Detecta swap/zRAM ativo."""
    try:
        with open("/proc/meminfo") as f:
            info = {}
            for line in f:
                if ":" in line:
                    k, v = line.split(":", 1)
                    info[k.strip()] = v.strip()
        swap_total = int(info.get("SwapTotal", "0 kB").split()[0])
        swap_free  = int(info.get("SwapFree",  "0 kB").split()[0])
        swap_used  = swap_total - swap_free
        if swap_used > 512 * 1024:
            return True, f"swap em uso: {swap_used//1024}MB"
    except Exception:
        pass
    return False, "ok"

def _physical_confidence(latencies, cold, hot, pf_ratio) -> float:
    """Score de confiança de RAM física (0.0 a 1.0)."""
    score = 1.0
    cv = _check_variance(latencies)
    # Penaliza variância muito baixa (RAM virtual uniforme)
    if cv < MIN_VARIANCE:
        score *= max(0.3, cv / MIN_VARIANCE)
    # Penaliza variância muito alta (swap)
    if cv > MAX_VARIANCE:
        score *= max(0.1, 1.0 - (cv - MAX_VARIANCE))
    # Thermal fingerprint
    thermal = hot / max(cold, 0.0001)
    if 1.03 <= thermal <= 1.40:
        score = min(1.0, score * 1.1)   # bônus: aqueceu normalmente
    elif thermal < 1.01:
        score *= 0.7                     # suspeito: não aqueceu
    # Page fault ratio
    if pf_ratio >= 1.15:
        score = min(1.0, score * 1.05)
    elif pf_ratio < 1.05:
        score *= 0.8
    return max(0.1, min(1.0, score))

def compute_ram_proof(
    seed: int,
    ram_mult: float,
    buf: Optional[bytearray] = None,
    ram_type: str = "AUTO",
    block_hash: str = "",
    height: int = 0,
    cpu_cores: int = 0,
) -> dict:
    """
    Prova de RAM física com anti-trapaça completo.
    Score = RAM_latency × RAM_mult × CPU_mult × confidence_física
    """
    from polm_core import get_ram_multiplier, get_cpu_multiplier, detect_cpu_cores

    if buf is None:
        buf = get_buffer()

    # Multiplicador de RAM pela época
    if height > 0:
        try:
            mult, allowed = get_ram_multiplier(ram_type, height)
            if allowed: ram_mult = mult
        except Exception:
            pass

    # Multiplicador de CPU
    if cpu_cores <= 0:
        cpu_cores = detect_cpu_cores()
    cpu_mult, _ = get_cpu_multiplier(cpu_cores, height)

    # Fase 1: Aquecimento térmico
    cold_lat, hot_lat = _check_thermal(buf)

    # Fase 2: Detecta swap
    has_swap, swap_reason = _check_swap()

    # Fase 3: Page fault pattern
    pf_ratio = _check_page_fault_pattern(buf)

    # Fase 4: Multi-round com seeds vinculados ao bloco
    seeds     = []
    latencies = []
    checksums = []
    for i in range(NUM_ROUNDS):
        h = hashlib.sha256(f"{seed}:{block_hash}:{i}".encode()).digest()
        s = int.from_bytes(h[:4], "big")
        seeds.append(s)
        work, lat = memory_storm(s, buf)
        latencies.append(lat)
        checksums.append(work)

    # Fase 5: Confiança física
    confidence = _physical_confidence(latencies, cold_lat, hot_lat, pf_ratio)
    if has_swap:
        confidence *= 0.3   # penalidade severa por swap

    # Fase 6: Score final
    avg_lat     = sum(latencies) / len(latencies)
    raw_score   = max(SCORE_MIN, min(SCORE_MAX, avg_lat * 1000.0 * ram_mult))
    final_score = max(SCORE_MIN, min(SCORE_MAX, raw_score * confidence * cpu_mult))

    combined = checksums[0]
    for c in checksums[1:]: combined ^= c

    return {
        "seed":             seed,
        "seeds":            seeds,
        "work":             combined,
        "latency":          round(avg_lat, 6),
        "latencies":        [round(l, 6) for l in latencies],
        "variance":         round(_check_variance(latencies), 4),
        "cold_latency":     round(cold_lat, 6),
        "hot_latency":      round(hot_lat, 6),
        "thermal_ratio":    round(hot_lat / max(cold_lat, 0.0001), 4),
        "page_fault_ratio": round(pf_ratio, 4),
        "confidence":       round(confidence, 4),
        "score":            round(final_score, 4),
        "ram_score":        round(raw_score, 4),
        "ram_mult":         round(ram_mult, 2),
        "cpu_mult":         round(cpu_mult, 2),
        "cpu_cores":        cpu_cores,
        "ram_type":         ram_type,
        "physical_ram_gb":  round(detect_physical_ram_gb(), 1),
        "is_suspicious":    has_swap,
        "suspicious_reason": swap_reason if has_swap else "",
    }

def verify_ram_proof(proof: dict, buf: Optional[bytearray] = None) -> Tuple[bool, str]:
    """Verificação completa — re-executa memory_storm e verifica checksums."""
    if buf is None:
        buf = get_buffer()
    seeds = proof.get("seeds", [proof.get("seed")])
    checksums = []
    for s in seeds:
        if s is None: return False, "seed ausente"
        work, _ = memory_storm(s, buf)
        checksums.append(work)
    combined = checksums[0]
    for c in checksums[1:]: combined ^= c
    if proof.get("work") != combined:
        return False, "checksum inválido"
    if proof.get("confidence", 1.0) < 0.3:
        return False, f"confiança RAM física baixa: {proof.get('confidence')}"
    if proof.get("variance", 0) > MAX_VARIANCE:
        return False, f"variância suspeita: {proof.get('variance')}"
    return True, "ok"

def verify_ram_proof_fast(proof: dict) -> Tuple[bool, str]:
    """Verificação rápida — checa plausibilidade dos valores."""
    latency    = proof.get("latency", 0)
    score      = proof.get("score", 0)
    confidence = proof.get("confidence", 1.0)
    variance   = proof.get("variance", 0)
    thermal    = proof.get("thermal_ratio", 1.0)
    if not (0 < latency < 120):
        return False, f"latência implausível: {latency}"
    if not (SCORE_MIN <= score <= SCORE_MAX):
        return False, f"score fora do intervalo: {score}"
    if confidence < 0.25:
        return False, f"confiança insuficiente: {confidence:.2f}"
    if variance > MAX_VARIANCE:
        return False, f"variância suspeita: {variance:.3f}"
    if thermal < 0.95:
        return False, f"thermal ratio suspeito: {thermal:.3f}"
    return True, "ok"

def benchmark_ram_speed(size_mb: int = 64) -> float:
    """Benchmark rápido de latência de RAM."""
    size = size_mb * 1024 * 1024
    buf  = bytearray(os.urandom(min(size, 4*1024*1024)))
    buf  = bytearray((buf * (size//len(buf)+1))[:size])
    t0   = time.perf_counter()
    total = 0
    for i in range(0, size, 4096): total += buf[i]
    elapsed = time.perf_counter() - t0
    return (size / (1024*1024)) / max(elapsed, 0.001)
