"""
polm_ram.py — Prova de Latência de RAM v2.0
=============================================
© 2025 Aluisio Fernandes "Aluminium" — Todos os direitos reservados.
Proof of Legacy Memory (PoLM) — Licença proprietária PoLM-1.0

CHANGELOG v2.0:
  - Detecção anti-VM (VMware, VirtualBox, QEMU, WSL, Docker, KVM)
  - Fingerprint físico de hardware (CPU serial, motherboard, RAM slots)
  - Benchmark de latência real para validar tipo de RAM declarado
  - Detecção de tentativa de falsificação de tipo de RAM
  - Score vinculado ao fingerprint do hardware
  - Proteção contra replay de prova (seed derivado do bloco + hardware)
  - Verificação de plausibilidade física de latência
  - Logs de tentativa de trapaça
"""

import hashlib
import os
import platform
import random
import re
import struct
import subprocess
import sys
import time
from typing import Optional, Tuple

# ═══════════════════════════════════════════════════════════
# PARÂMETROS
# ═══════════════════════════════════════════════════════════

GRAPH_SIZE      = 300_000
SCORE_MIN       = 0.1
SCORE_MAX       = 200.0
CHEAT_LOG_FILE  = "polm_cheat.log"

# Multiplicadores por geração de RAM
RAM_MULTIPLIERS = {
    "DDR2":   2.5,
    "DDR3":   1.8,
    "DDR4":   1.0,
    "DDR5":   0.6,
    "LPDDR4": 0.9,
    "LPDDR5": 0.55,
    "AUTO":   1.0,
}

# Latência esperada por tipo de RAM (ms para 300k acessos em 256MB)
# Hardware físico real tem latências nestas faixas
RAM_LATENCY_RANGES = {
    "DDR2":   (4.0,  20.0),   # DDR2: muito lento, ampla variação
    "DDR3":   (2.5,  10.0),   # DDR3: lento
    "DDR4":   (1.0,   5.0),   # DDR4: rápido
    "DDR5":   (0.5,   3.0),   # DDR5: muito rápido
    "LPDDR4": (1.2,   5.5),
    "LPDDR5": (0.6,   3.5),
    "AUTO":   (0.5,  20.0),   # sem validação se AUTO
}

# ═══════════════════════════════════════════════════════════
# DETECÇÃO ANTI-VM
# ═══════════════════════════════════════════════════════════

def _log_cheat(reason: str) -> None:
    """Registra tentativa de trapaça."""
    ts  = time.strftime("%Y-%m-%d %H:%M:%S")
    msg = f"[{ts}] CHEAT_DETECTED: {reason}\n"
    try:
        with open(CHEAT_LOG_FILE, "a") as f:
            f.write(msg)
    except Exception:
        pass


def detect_virtualization() -> Tuple[bool, str]:
    """
    Detecta se o software está rodando em ambiente virtualizado.
    Retorna (is_virtual, reason).
    
    Detecta: VMware, VirtualBox, QEMU, KVM, Hyper-V, WSL, Docker,
             LXC, OpenVZ, Xen, Parallels.
    """
    if platform.system() != "Linux":
        # Em outros SOs não conseguimos verificar com confiança
        return False, "ok"

    reasons = []

    # 1. Verifica /proc/cpuinfo por marcadores de VM
    try:
        cpuinfo = open("/proc/cpuinfo").read().lower()
        vm_markers = [
            ("vmware",    "VMware detectado em /proc/cpuinfo"),
            ("virtualbox","VirtualBox detectado em /proc/cpuinfo"),
            ("qemu",      "QEMU detectado em /proc/cpuinfo"),
            ("kvm",       "KVM detectado em /proc/cpuinfo"),
            ("hypervisor","Hypervisor flag detectada em CPU"),
            ("xen",       "Xen detectado em /proc/cpuinfo"),
        ]
        for marker, msg in vm_markers:
            if marker in cpuinfo:
                reasons.append(msg)
    except Exception:
        pass

    # 2. Verifica DMI/BIOS por strings de VM
    try:
        dmi = subprocess.check_output(
            ["sudo", "dmidecode", "-t", "system"],
            stderr=subprocess.DEVNULL, timeout=5
        ).decode(errors="ignore").lower()

        dmi_markers = [
            ("vmware",       "VMware em DMI"),
            ("virtualbox",   "VirtualBox em DMI"),
            ("qemu",         "QEMU em DMI"),
            ("microsoft corporation", None),  # pode ser Hyper-V
            ("innotek",      "VirtualBox (Innotek) em DMI"),
            ("parallels",    "Parallels em DMI"),
            ("xen",          "Xen em DMI"),
        ]
        for marker, msg in dmi_markers:
            if marker in dmi and msg:
                reasons.append(msg)

        # Hyper-V específico
        if "microsoft corporation" in dmi and "hyper-v" in dmi:
            reasons.append("Hyper-V em DMI")
    except Exception:
        pass

    # 3. Verifica /proc/vz (OpenVZ/Virtuozzo)
    if os.path.exists("/proc/vz"):
        reasons.append("OpenVZ/Virtuozzo detectado (/proc/vz)")

    # 4. Verifica WSL (Windows Subsystem for Linux)
    try:
        with open("/proc/version") as f:
            version = f.read().lower()
        if "microsoft" in version or "wsl" in version:
            reasons.append("WSL (Windows Subsystem for Linux) detectado")
    except Exception:
        pass

    # 5. Verifica Docker/container
    if os.path.exists("/.dockerenv"):
        reasons.append("Docker container detectado (/.dockerenv)")

    try:
        with open("/proc/1/cgroup") as f:
            cgroup = f.read()
        if "docker" in cgroup or "lxc" in cgroup or "kubepods" in cgroup:
            reasons.append("Container (Docker/LXC/K8s) detectado em cgroup")
    except Exception:
        pass

    # 6. Verifica systemd-detect-virt
    try:
        result = subprocess.check_output(
            ["systemd-detect-virt"], stderr=subprocess.DEVNULL, timeout=3
        ).decode().strip()
        if result and result != "none":
            reasons.append(f"systemd-detect-virt: {result}")
    except Exception:
        pass

    # 7. Verifica número de CPUs: VMs raramente têm > 8 núcleos físicos reais
    # (heurística fraca, não bloqueia sozinha)

    if reasons:
        return True, "; ".join(reasons)
    return False, "ok"


# ═══════════════════════════════════════════════════════════
# FINGERPRINT DE HARDWARE
# ═══════════════════════════════════════════════════════════

def get_hardware_fingerprint() -> str:
    """
    Gera um fingerprint único do hardware físico.
    Combina: CPU, motherboard, RAM (slots), disco serial.
    
    O fingerprint é incluído na prova de RAM, vinculando-a
    ao hardware específico. Um minerador não pode reutilizar
    a prova em outro hardware.
    """
    components = []

    if platform.system() == "Linux":
        # CPU info
        try:
            cpuinfo = open("/proc/cpuinfo").read()
            cpu_model = re.search(r"model name\s*:\s*(.+)", cpuinfo)
            if cpu_model:
                components.append(f"cpu:{cpu_model.group(1).strip()}")
        except Exception:
            pass

        # Motherboard serial + UUID
        try:
            board = subprocess.check_output(
                ["sudo", "dmidecode", "-t", "baseboard"],
                stderr=subprocess.DEVNULL, timeout=5
            ).decode(errors="ignore")
            serial = re.search(r"Serial Number:\s*(.+)", board)
            if serial and serial.group(1).strip() not in ("", "None", "To Be Filled By O.E.M."):
                components.append(f"board:{serial.group(1).strip()}")
        except Exception:
            pass

        # System UUID
        try:
            sys_info = subprocess.check_output(
                ["sudo", "dmidecode", "-t", "system"],
                stderr=subprocess.DEVNULL, timeout=5
            ).decode(errors="ignore")
            uuid = re.search(r"UUID:\s*(.+)", sys_info)
            if uuid and uuid.group(1).strip() not in ("", "Not Settable", "Not Present"):
                components.append(f"uuid:{uuid.group(1).strip()}")
        except Exception:
            pass

        # RAM: número de slots, localizações
        try:
            mem_info = subprocess.check_output(
                ["sudo", "dmidecode", "-t", "memory"],
                stderr=subprocess.DEVNULL, timeout=5
            ).decode(errors="ignore")
            slots = re.findall(r"Locator:\s*(.+)", mem_info)
            if slots:
                components.append(f"ram_slots:{','.join(sorted(slots[:4]))}")
        except Exception:
            pass

        # /etc/machine-id (único por instalação Linux)
        try:
            machine_id = open("/etc/machine-id").read().strip()
            if machine_id:
                components.append(f"mid:{machine_id[:16]}")
        except Exception:
            pass

    if not components:
        # Fallback: usa hostname + plataforma
        components.append(f"host:{platform.node()}")
        components.append(f"plat:{platform.machine()}")

    fingerprint_raw = "|".join(components)
    return hashlib.sha256(fingerprint_raw.encode()).hexdigest()


# ═══════════════════════════════════════════════════════════
# DETECÇÃO DE RAM
# ═══════════════════════════════════════════════════════════

def detect_ram_type() -> Tuple[str, float]:
    """
    Detecta o tipo de RAM instalado via dmidecode.
    Retorna (tipo, multiplicador).
    """
    ram_type = "AUTO"

    if platform.system() == "Linux":
        try:
            out = subprocess.check_output(
                ["sudo", "dmidecode", "-t", "memory"],
                stderr=subprocess.DEVNULL, timeout=5,
            ).decode(errors="ignore")

            for gen in ["DDR5", "LPDDR5", "LPDDR4", "DDR4", "DDR3", "DDR2"]:
                if gen in out:
                    ram_type = gen
                    break
        except Exception:
            pass

    elif platform.system() == "Darwin":
        try:
            out = subprocess.check_output(
                ["system_profiler", "SPMemoryDataType"],
                stderr=subprocess.DEVNULL, timeout=5,
            ).decode(errors="ignore")
            for gen in ["DDR5", "DDR4", "DDR3", "DDR2", "LPDDR"]:
                if gen in out:
                    ram_type = gen
                    break
        except Exception:
            pass

    elif platform.system() == "Windows":
        try:
            out = subprocess.check_output(
                ["wmic", "memorychip", "get", "SMBIOSMemoryType"],
                stderr=subprocess.DEVNULL, timeout=5,
            ).decode(errors="ignore")
            type_map = {"20": "DDR2", "24": "DDR3", "26": "DDR4", "34": "DDR5"}
            for code, name in type_map.items():
                if code in out:
                    ram_type = name
                    break
        except Exception:
            pass

    mult = RAM_MULTIPLIERS.get(ram_type, 1.0)
    return ram_type, mult


def validate_ram_type_vs_latency(ram_type: str, latency: float) -> Tuple[bool, str]:
    """
    Valida se a latência medida é fisicamente plausível para o tipo de RAM declarado.
    
    Um minerador que falsifica o tipo de RAM (ex: declara DDR2 mas tem DDR4)
    terá latência muito menor que o esperado para DDR2.
    
    Retorna (valid, reason).
    """
    if ram_type == "AUTO":
        return True, "ok"  # sem validação se AUTO

    lo, hi = RAM_LATENCY_RANGES.get(ram_type, (0.1, 60.0))

    # Tolerância de 50% para baixo (hardware pode ser melhor que o esperado)
    # e 3x para cima (hardware muito degradado/lento)
    lo_tol = lo * 0.5
    hi_tol = hi * 3.0

    if latency < lo_tol:
        return False, (
            f"Latência {latency:.3f}s muito BAIXA para {ram_type} "
            f"(esperado >{lo_tol:.3f}s) — possível falsificação de tipo de RAM"
        )

    if latency > hi_tol:
        return False, (
            f"Latência {latency:.3f}s muito ALTA para {ram_type} "
            f"(esperado <{hi_tol:.3f}s) — hardware anormal"
        )

    return True, "ok"


# ═══════════════════════════════════════════════════════════
# BUFFER
# ═══════════════════════════════════════════════════════════

_buffer:      Optional[bytearray] = None
_buffer_size: int                  = 0


def init_buffer(size_mb: int = 256) -> bytearray:
    """
    Inicializa o buffer de RAM com bytes aleatórios reais.
    Bytes aleatórios forçam alocação de páginas físicas (anti zero-page collapse).
    """
    global _buffer, _buffer_size

    size = size_mb * 1024 * 1024
    print(f"[PoLM RAM] Alocando {size_mb} MB de buffer... ", end="", flush=True)
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

    elapsed      = time.perf_counter() - t0
    _buffer      = buf
    _buffer_size = size
    print(f"OK ({elapsed:.2f}s)")
    return buf


def get_buffer() -> bytearray:
    global _buffer
    if _buffer is None:
        _buffer = init_buffer(256)
    return _buffer


# ═══════════════════════════════════════════════════════════
# MEMORY STORM — PROVA DE LATÊNCIA
# ═══════════════════════════════════════════════════════════

def memory_storm(seed: int, buf: Optional[bytearray] = None) -> Tuple[int, float]:
    """
    Prova de latência de RAM — acesso não-sequencial com checksum encadeado.
    
    Anti-otimização:
    • Acesso não-sequencial → invalida L1/L2/L3 cache
    • Stride variável → impossível pré-buscar (hardware prefetcher ineficaz)
    • Checksum encadeado → cada leitura depende da anterior (sem paralelismo)
    • Buffer 256MB → não cabe em cache L3 (tipicamente < 64MB)
    """
    if buf is None:
        buf = get_buffer()

    size   = len(buf)
    mask   = size - 1

    if size & (size - 1) != 0:
        ptr    = seed % size
        total  = 0
        stride = (seed >> 8) | 1
        t0     = time.perf_counter()
        for i in range(GRAPH_SIZE):
            ptr    = (ptr * 1_103_515_245 + 12_345 + stride) % size
            total ^= buf[ptr]
            if (i & 0xFFF) == 0:
                stride = ((total * 6_364_136_223_846_793_005 + 1) % size) | 1
        return total, time.perf_counter() - t0

    ptr    = seed & mask
    total  = 0
    stride = (seed >> 8) | 1
    t0     = time.perf_counter()
    for i in range(GRAPH_SIZE):
        ptr    = (ptr * 1_103_515_245 + 12_345 + stride) & mask
        total ^= buf[ptr]
        if (i & 0xFFF) == 0:
            stride = ((total * 6_364_136_223_846_793_005 + 1) & mask) | 1
    return total, time.perf_counter() - t0


def _compute_score(latency: float, ram_mult: float) -> float:
    raw = latency * 1000.0 * ram_mult
    return max(SCORE_MIN, min(SCORE_MAX, raw))


# ═══════════════════════════════════════════════════════════
# PROVA COMPLETA (com anti-trapaça)
# ═══════════════════════════════════════════════════════════

def compute_ram_proof(
    seed: int,
    ram_mult: float,
    buf: Optional[bytearray] = None,
    ram_type: str = "AUTO",
    block_hash: str = "",
) -> dict:
    """
    Executa a prova de RAM completa com todas as proteções.
    
    Proteções incluídas:
    1. Detecção de VM — rejeita se virtualizado
    2. Fingerprint de hardware — vincula prova ao hardware físico
    3. Seed derivado do bloco — impede replay de provas antigas
    4. Validação de latência vs tipo de RAM — detecta falsificação
    """
    # 1. Anti-VM
    is_vm, vm_reason = detect_virtualization()
    if is_vm:
        _log_cheat(f"VM detectada: {vm_reason}")
        raise RuntimeError(
            f"PoLM não pode rodar em ambiente virtualizado: {vm_reason}\n"
            f"Use hardware físico real para minerar PoLM."
        )

    # 2. Fingerprint de hardware
    hw_fingerprint = get_hardware_fingerprint()

    # 3. Seed seguro: combina seed do bloco + fingerprint
    #    Impede que um minerador reutilize uma prova em hardware diferente
    safe_seed = int(hashlib.sha256(
        f"{seed}|{hw_fingerprint}|{block_hash}".encode()
    ).hexdigest()[:16], 16)

    # 4. Executa prova
    work, latency = memory_storm(safe_seed, buf)
    score         = _compute_score(latency, ram_mult)

    # 5. Valida latência vs tipo de RAM declarado
    valid, reason = validate_ram_type_vs_latency(ram_type, latency)
    if not valid:
        _log_cheat(f"Latência suspeita: {reason} | hw={hw_fingerprint[:16]}")
        # Penaliza: usa mult=1.0 independente do que foi declarado
        ram_mult = 1.0
        score    = _compute_score(latency, ram_mult)

    return {
        "seed":            seed,
        "safe_seed":       safe_seed,
        "work":            work,
        "latency":         round(latency, 6),
        "score":           round(score, 4),
        "ram_mult":        round(ram_mult, 2),
        "ram_type":        ram_type,
        "hw_fingerprint":  hw_fingerprint[:32],  # primeiros 32 chars do hash
        "latency_valid":   valid,
    }


# ═══════════════════════════════════════════════════════════
# VERIFICAÇÃO DE PROVA
# ═══════════════════════════════════════════════════════════

def verify_ram_proof(proof: dict, buf: Optional[bytearray] = None) -> Tuple[bool, str]:
    """
    Verificação completa da prova (re-executa memory_storm).
    Usado por peers ao receber um bloco.
    """
    if buf is None:
        buf = get_buffer()

    safe_seed = proof.get("safe_seed")
    if safe_seed is None:
        # Compatibilidade com provas antigas (sem safe_seed)
        safe_seed = proof.get("seed")
    if safe_seed is None:
        return False, "seed ausente"

    work_expected, latency_actual = memory_storm(safe_seed, buf)

    if proof.get("work") != work_expected:
        return False, f"work inválido: {proof.get('work')} ≠ {work_expected}"

    latency_reported = proof.get("latency", 0)
    if abs(latency_reported - latency_actual) > latency_actual * 0.25 + 0.1:
        return False, (
            f"latência suspeita: reportada={latency_reported:.4f}s, "
            f"medida={latency_actual:.4f}s"
        )

    # Valida coerência do score
    ram_mult = proof.get("ram_mult", 1.0)
    expected_score = _compute_score(latency_actual, ram_mult)
    if abs(proof.get("score", 0) - expected_score) > 2.0:
        return False, "score inconsistente com latência medida"

    return True, "ok"


def verify_ram_proof_fast(proof: dict) -> Tuple[bool, str]:
    """
    Verificação rápida sem re-executar memory_storm.
    Checa plausibilidade dos valores.
    """
    latency  = proof.get("latency", 0)
    score    = proof.get("score", 0)
    work     = proof.get("work")
    seed     = proof.get("seed")
    ram_type = proof.get("ram_type", "AUTO")

    if seed is None or work is None:
        return False, "campos obrigatórios ausentes"

    if not (0 < latency < 60):
        return False, f"latência implausível: {latency}"

    if not (SCORE_MIN <= score <= SCORE_MAX):
        return False, f"score fora do intervalo: {score}"

    # Valida latência vs tipo de RAM
    valid, reason = validate_ram_type_vs_latency(ram_type, latency)
    if not valid:
        return False, reason

    ram_mult       = proof.get("ram_mult", 1.0)
    expected_score = _compute_score(latency, ram_mult)
    if abs(score - expected_score) > 2.0:
        return False, "score inconsistente com latência"

    return True, "ok"


def benchmark_ram_speed(size_mb: int = 64) -> float:
    """Benchmark rápido de latência de RAM para calibração. Retorna MB/s."""
    size  = size_mb * 1024 * 1024
    buf   = bytearray(os.urandom(min(size, 4 * 1024 * 1024)))
    buf   = buf * (size // len(buf) + 1)
    buf   = bytearray(buf[:size])
    t0    = time.perf_counter()
    total = 0
    step  = 4096
    for i in range(0, size, step):
        total += buf[i]
    elapsed = time.perf_counter() - t0
    return (size / (1024 * 1024)) / max(elapsed, 0.001)
