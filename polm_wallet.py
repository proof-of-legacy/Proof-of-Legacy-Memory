"""
polm_wallet.py — PoLM Wallet
==============================
Carteira HD (Hierarchical Deterministic) estilo Bitcoin.

Funcionalidades:
  • Geração de seed mnemônica de 24 palavras (BIP-39 simplificado)
  • Derivação de par de chaves ECDSA (secp256k1 via biblioteca)
  • Endereços com checksum (estilo Bitcoin Base58Check)
  • Assinatura e verificação de transações
  • Múltiplos endereços derivados da mesma seed
  • Import/export em formato JSON criptografado
  • CLI completo

Uso:
    python3 polm_wallet.py create
    python3 polm_wallet.py balance --address <addr>
    python3 polm_wallet.py send --to <addr> --amount <polm> --fee <polm>
    python3 polm_wallet.py receive
    python3 polm_wallet.py history
    python3 polm_wallet.py export --password <pwd>
    python3 polm_wallet.py import --file wallet_backup.json
"""

import argparse
import base64
import hashlib
import hmac
import json
import os
import secrets
import struct
import sys
import time
from typing import Optional
from polm_core import COIN, CHAIN_ID

# ─── Tenta importar bibliotecas criptográficas ──────────────
try:
    from ecdsa import SigningKey, VerifyingKey, SECP256k1, BadSignatureError
    _HAS_ECDSA = True
except ImportError:
    _HAS_ECDSA = False

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes as _hashes
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False

from polm_core import (
    COIN, MAX_SUPPLY_COINS, WALLET_FILE, sha256d, sha256d_hex,
    hash_transaction, DEFAULT_PORT
)

# ═══════════════════════════════════════════════════════════
# BASE58CHECK (igual ao Bitcoin)
# ═══════════════════════════════════════════════════════════

BASE58_ALPHABET = b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

ADDRESS_PREFIX  = b"\x19"   # gera endereços começando com "P"


def _base58_encode(data: bytes) -> str:
    count = 0
    for byte in data:
        if byte == 0:
            count += 1
        else:
            break
    num     = int.from_bytes(data, "big")
    result  = []
    while num > 0:
        num, rem = divmod(num, 58)
        result.append(BASE58_ALPHABET[rem:rem+1])
    return (BASE58_ALPHABET[0:1] * count + b"".join(reversed(result))).decode()


def _base58_decode(s: str) -> bytes:
    count  = 0
    for c in s:
        if c == "1":
            count += 1
        else:
            break
    num = 0
    for c in s:
        num = num * 58 + BASE58_ALPHABET.index(c.encode())
    result = num.to_bytes(max((num.bit_length() + 7) // 8, 1), "big")
    return b"\x00" * count + result


def _base58check_encode(payload: bytes, prefix: bytes) -> str:
    data     = prefix + payload
    checksum = sha256d(data)[:4]
    return _base58_encode(data + checksum)


def _base58check_decode(s: str) -> tuple[bytes, bytes]:
    """Retorna (prefix, payload) ou lança ValueError se checksum falhar."""
    raw      = _base58_decode(s)
    payload  = raw[:-4]
    checksum = raw[-4:]
    computed = sha256d(payload)[:4]
    if computed != checksum:
        raise ValueError("Checksum inválido")
    prefix  = payload[:1]
    data    = payload[1:]
    return prefix, data

# ═══════════════════════════════════════════════════════════
# MNEMÔNICA (BIP-39 simplificado)
# ═══════════════════════════════════════════════════════════

# 2048 palavras BIP-39 (primeiras 256 para uso interno)
_WORDLIST = [
    "abandon","ability","able","about","above","absent","absorb","abstract",
    "absurd","abuse","access","accident","account","accuse","achieve","acid",
    "acoustic","acquire","across","act","action","actor","actress","actual",
    "adapt","add","addict","address","adjust","admit","adult","advance",
    "advice","aerobic","afford","afraid","again","agent","agree","ahead",
    "aim","air","airport","aisle","alarm","album","alcohol","alert","alien",
    "all","alley","allow","almost","alone","alpha","already","also","alter",
    "always","amateur","amazing","among","amount","amused","analyst","anchor",
    "anger","angle","angry","animal","ankle","announce","annual","another",
    "answer","antenna","antique","anxiety","any","apart","apology","appear",
    "apple","approve","april","arch","arctic","area","arena","argue","arm",
    "armed","armor","army","around","arrange","arrest","arrive","arrow","art",
    "artefact","artist","artwork","ask","aspect","assault","asset","assist",
    "assume","asthma","athlete","atom","attack","attend","attitude","attract",
    "auction","audit","august","aunt","author","auto","autumn","average",
    "avocado","avoid","awake","aware","away","awesome","awful","awkward",
    "axis","baby","balance","bamboo","banana","banner","barely","bargain",
    "barrel","base","basic","basket","battle","beach","bean","beauty","become",
    "beef","before","begin","behave","behind","believe","below","belt","bench",
    "benefit","best","betray","better","between","beyond","bicycle","bid",
    "bike","bind","biology","bird","birth","bitter","black","blade","blame",
    "blanket","blast","bleak","bless","blind","blood","blossom","blouse","blue",
    "blur","blush","board","boat","body","boil","bomb","bone","book","boost",
    "border","boring","borrow","boss","bottom","bounce","box","boy","bracket",
    "brain","brand","brave","breeze","brick","bridge","brief","bright","bring",
    "brisk","broccoli","broken","bronze","broom","brother","brown","brush",
    "bubble","buddy","budget","buffalo","build","bulb","bulk","bullet","bundle",
    "bunker","burden","burger","burst","bus","business","busy","butter","buyer",
]

# Padding para ter exatamente 256 palavras disponíveis
while len(_WORDLIST) < 256:
    _WORDLIST.append(f"word{len(_WORDLIST)}")

_WORDLIST_2048 = _WORDLIST * 8   # simplificado para não incluir arquivo externo


def generate_mnemonic(strength: int = 256) -> str:
    """
    Gera mnemônica de 24 palavras a partir de 256 bits de entropia.
    Em produção use a wordlist BIP-39 completa de 2048 palavras.
    """
    entropy = secrets.token_bytes(strength // 8)
    # Checksum: primeiros (strength/32) bits do SHA-256 da entropia
    checksum_bits = strength // 32
    checksum      = int(hashlib.sha256(entropy).hexdigest(), 16)
    checksum_val  = checksum >> (256 - checksum_bits)

    # Converte entropia + checksum em grupos de 11 bits
    bits       = int.from_bytes(entropy, "big")
    bits       = (bits << checksum_bits) | checksum_val
    total_bits = strength + checksum_bits
    word_count = total_bits // 11

    words = []
    for i in range(word_count - 1, -1, -1):
        idx = (bits >> (i * 11)) & 0x7FF
        words.append(_WORDLIST_2048[idx % len(_WORDLIST_2048)])

    return " ".join(words)


def mnemonic_to_seed(mnemonic: str, passphrase: str = "") -> bytes:
    """Deriva seed de 64 bytes a partir da mnemônica (PBKDF2-HMAC-SHA512)."""
    salt   = ("mnemonic" + passphrase).encode("utf-8")
    return hashlib.pbkdf2_hmac(
        "sha512",
        mnemonic.encode("utf-8"),
        salt,
        iterations=2048,
        dklen=64,
    )

# ═══════════════════════════════════════════════════════════
# CHAVES E ENDEREÇOS
# ═══════════════════════════════════════════════════════════

def _derive_privkey(seed: bytes, index: int = 0) -> bytes:
    """Deriva chave privada da seed usando HMAC-SHA512 (BIP-32 simplificado)."""
    data   = seed + struct.pack(">I", index)
    result = hmac.new(b"PoLM seed", data, hashlib.sha512).digest()
    # Metade esquerda = chave privada; metade direita = chain code
    privkey = result[:32]
    # Garante que está no range secp256k1
    n = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
    val = int.from_bytes(privkey, "big") % n
    return val.to_bytes(32, "big")


def privkey_to_pubkey(privkey: bytes) -> bytes:
    """Deriva chave pública comprimida (33 bytes) a partir da privada."""
    if _HAS_ECDSA:
        sk = SigningKey.from_string(privkey, curve=SECP256k1)
        vk = sk.get_verifying_key()
        # Formato comprimido
        x = vk.pubkey.point.x()
        y = vk.pubkey.point.y()
        prefix = b"\x02" if y % 2 == 0 else b"\x03"
        return prefix + x.to_bytes(32, "big")
    else:
        # Fallback sem ecdsa: usa hash da privada (NÃO seguro para produção)
        return b"\x02" + hashlib.sha256(privkey).digest()


def pubkey_to_address(pubkey: bytes) -> str:
    """
    Deriva endereço PoLM a partir da chave pública.
    Processo: SHA256 → RIPEMD160 → Base58Check com prefixo PoLM
    """
    sha    = hashlib.sha256(pubkey).digest()
    rmd    = hashlib.new("ripemd160", sha).digest()
    return _base58check_encode(rmd, ADDRESS_PREFIX)


def validate_address(addr: str) -> bool:
    """Verifica se um endereço PoLM é válido (checksum correto)."""
    try:
        prefix, _ = _base58check_decode(addr)
        return prefix == ADDRESS_PREFIX
    except Exception:
        return False

# ═══════════════════════════════════════════════════════════
# ASSINATURA ECDSA
# ═══════════════════════════════════════════════════════════

def sign_tx(tx: dict, privkey_hex: str) -> dict:
    """
    Assina todos os inputs de uma transação com a chave privada.
    Retorna a transação com campo 'signatures' preenchido.
    """
    privkey  = bytes.fromhex(privkey_hex)
    tx_clean = {k: v for k, v in tx.items() if k not in ("signatures", "txid")}
    msg      = json.dumps(tx_clean, sort_keys=True, separators=(",", ":")).encode()
    msg_hash = sha256d(msg)

    if _HAS_ECDSA:
        sk  = SigningKey.from_string(privkey, curve=SECP256k1)
        sig = sk.sign_digest(msg_hash, sigencode=_sigencode_der)
    else:
        # Fallback HMAC (NÃO é ECDSA real — apenas para testes sem biblioteca)
        sig = hmac.new(privkey, msg_hash, hashlib.sha256).digest()

    pubkey = privkey_to_pubkey(privkey)
    tx["signatures"] = [{
        "pubkey": pubkey.hex(),
        "sig":    sig.hex(),
    }]
    tx["txid"] = hash_transaction(tx)
    return tx


def verify_tx_signature(tx: dict) -> bool:
    """Verifica as assinaturas de uma transação."""
    sigs = tx.get("signatures", [])
    if not sigs:
        return False

    tx_clean = {k: v for k, v in tx.items() if k not in ("signatures", "txid")}
    msg      = json.dumps(tx_clean, sort_keys=True, separators=(",", ":")).encode()
    msg_hash = sha256d(msg)

    for sig_entry in sigs:
        try:
            pubkey_bytes = bytes.fromhex(sig_entry["pubkey"])
            sig_bytes    = bytes.fromhex(sig_entry["sig"])

            if _HAS_ECDSA:
                vk = VerifyingKey.from_string(pubkey_bytes[1:], curve=SECP256k1)
                vk.verify_digest(sig_bytes, msg_hash, sigdecode=_sigdecode_der)
            else:
                pass  # fallback: aceita (somente para testes)

        except Exception:
            return False

    return True


def _sigencode_der(r, s, order):
    """Codifica (r, s) em DER."""
    def encode_int(n):
        b = n.to_bytes((n.bit_length() + 7) // 8 or 1, "big")
        if b[0] & 0x80:
            b = b"\x00" + b
        return bytes([0x02, len(b)]) + b
    ri, si = encode_int(r), encode_int(s)
    return bytes([0x30, len(ri) + len(si)]) + ri + si


def _sigdecode_der(sig, order):
    """Decodifica DER em (r, s)."""
    if sig[0] != 0x30:
        raise ValueError
    seq  = sig[2:]
    r_len = seq[1]
    r     = int.from_bytes(seq[2: 2 + r_len], "big")
    rest  = seq[2 + r_len:]
    s_len = rest[1]
    s     = int.from_bytes(rest[2: 2 + s_len], "big")
    return r, s

def verify_tx_signature(tx: dict) -> bool:
    """
    Verifica todas as assinaturas ECDSA de uma transação.
    Retorna True se todas forem válidas.
    """
    from polm_core import hash_transaction
    sigs = tx.get("signatures", [])
    if not sigs:
        return False

    txid = hash_transaction(tx)
    msg  = bytes.fromhex(txid)

    for sig_entry in sigs:
        try:
            pubkey_hex = sig_entry["pubkey"]
            sig_hex    = sig_entry["sig"]
            if _HAS_ECDSA:
                vk  = VerifyingKey.from_string(bytes.fromhex(pubkey_hex), curve=SECP256k1)
                sig = bytes.fromhex(sig_hex)
                vk.verify_digest(sig, msg, sigdecode=_sigdecode_der)
            else:
                # Sem biblioteca ECDSA não podemos verificar — rejeita
                return False
        except Exception:
            return False
    return True


# ═══════════════════════════════════════════════════════════
# WALLET — ESTRUTURA E PERSISTÊNCIA
# ═══════════════════════════════════════════════════════════

class PoLMWallet:
    """Carteira HD com múltiplos endereços derivados da mesma seed."""

    def __init__(self):
        self.mnemonic:   str        = ""
        self.seed:       bytes      = b""
        self.accounts:   list[dict] = []   # [{index, privkey, pubkey, address}]
        self.label:      str        = "default"
        self.created_at: float      = time.time()

    # ── Criação ──────────────────────────────────────────

    @classmethod
    def create_new(cls, passphrase: str = "") -> "PoLMWallet":
        w             = cls()
        w.mnemonic    = generate_mnemonic(256)
        w.seed        = mnemonic_to_seed(w.mnemonic, passphrase)
        w.created_at  = time.time()
        w._derive_accounts(5)   # deriva 5 endereços iniciais
        return w

    @classmethod
    def from_mnemonic(cls, mnemonic: str, passphrase: str = "") -> "PoLMWallet":
        w          = cls()
        w.mnemonic = mnemonic.strip()
        w.seed     = mnemonic_to_seed(w.mnemonic, passphrase)
        w._derive_accounts(5)
        return w

    def _derive_accounts(self, count: int) -> None:
        for i in range(len(self.accounts), len(self.accounts) + count):
            priv = _derive_privkey(self.seed, i)
            pub  = privkey_to_pubkey(priv)
            addr = pubkey_to_address(pub)
            self.accounts.append({
                "index":   i,
                "privkey": priv.hex(),
                "pubkey":  pub.hex(),
                "address": addr,
            })

    def derive_more(self, n: int = 1) -> list[str]:
        self._derive_accounts(n)
        return [a["address"] for a in self.accounts[-n:]]

    # ── Endereços ────────────────────────────────────────

    @property
    def primary_address(self) -> str:
        return self.accounts[0]["address"] if self.accounts else ""

    def get_addresses(self) -> list[str]:
        return [a["address"] for a in self.accounts]

    def get_account_by_address(self, address: str) -> Optional[dict]:
        for acc in self.accounts:
            if acc["address"] == address:
                return acc
        return None

    # ── Assinatura ───────────────────────────────────────

    def sign(self, tx: dict, address: Optional[str] = None) -> dict:
        addr = address or self.primary_address
        acc  = self.get_account_by_address(addr)
        if not acc:
            raise ValueError(f"Endereço {addr} não encontrado na wallet")
        return sign_tx(tx, acc["privkey"])

    # ── Serialização ─────────────────────────────────────

    def to_dict(self, include_privkeys: bool = True) -> dict:
        accounts = []
        for a in self.accounts:
            entry = {"index": a["index"], "pubkey": a["pubkey"], "address": a["address"]}
            if include_privkeys:
                entry["privkey"] = a["privkey"]
            accounts.append(entry)
        return {
            "version":    1,
            "label":      self.label,
            "mnemonic":   self.mnemonic if include_privkeys else "",
            "accounts":   accounts,
            "created_at": self.created_at,
        }

    def save(self, path: str = WALLET_FILE) -> None:
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        os.replace(tmp, path)

    @classmethod
    def load(cls, path: str = WALLET_FILE) -> "PoLMWallet":
        with open(path) as f:
            data = json.load(f)
        w            = cls()
        w.label      = data.get("label", "default")
        w.mnemonic   = data.get("mnemonic", "")
        w.created_at = data.get("created_at", 0)
        w.accounts   = data.get("accounts", [])
        if w.mnemonic:
            w.seed = mnemonic_to_seed(w.mnemonic)
        return w

    # ── Export criptografado ──────────────────────────────

    def export_encrypted(self, password: str) -> dict:
        if not _HAS_CRYPTO:
            raise RuntimeError("Instale 'cryptography': pip install cryptography")

        plaintext = json.dumps(self.to_dict(), separators=(",", ":")).encode()
        salt      = os.urandom(16)
        kdf       = PBKDF2HMAC(
            algorithm=_hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=600_000,
        )
        key       = kdf.derive(password.encode())
        aesgcm    = AESGCM(key)
        nonce     = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)

        return {
            "version":    1,
            "kdf":        "pbkdf2-sha256",
            "iterations": 600_000,
            "salt":       salt.hex(),
            "nonce":      nonce.hex(),
            "ciphertext": ciphertext.hex(),
        }

    @classmethod
    def import_encrypted(cls, data: dict, password: str) -> "PoLMWallet":
        if not _HAS_CRYPTO:
            raise RuntimeError("Instale 'cryptography': pip install cryptography")

        salt       = bytes.fromhex(data["salt"])
        nonce      = bytes.fromhex(data["nonce"])
        ciphertext = bytes.fromhex(data["ciphertext"])
        kdf        = PBKDF2HMAC(
            algorithm=_hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=data.get("iterations", 600_000),
        )
        key       = kdf.derive(password.encode())
        aesgcm    = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        raw       = json.loads(plaintext.decode())

        w            = cls()
        w.label      = raw.get("label", "default")
        w.mnemonic   = raw.get("mnemonic", "")
        w.created_at = raw.get("created_at", 0)
        w.accounts   = raw.get("accounts", [])
        if w.mnemonic:
            w.seed = mnemonic_to_seed(w.mnemonic)
        return w

    def __repr__(self) -> str:
        return (
            f"PoLMWallet(label={self.label!r}, "
            f"addresses={len(self.accounts)}, "
            f"primary={self.primary_address[:16]}…)"
        )

# ═══════════════════════════════════════════════════════════
# CRIAÇÃO DE TRANSAÇÃO
# ═══════════════════════════════════════════════════════════

def build_tx(
    wallet: PoLMWallet,
    from_address: str,
    to_address: str,
    amount_sats: int,
    fee_sats: int,
    utxos: list[dict],
) -> dict:
    """
    Constrói e assina uma transação.
    
    utxos: lista de UTXOs disponíveis no endereço de origem.
           Formato: [{"txid": str, "vout": int, "value": int}, ...]
    """
    if not validate_address(to_address):
        raise ValueError(f"Endereço destino inválido: {to_address}")

    total_needed = amount_sats + fee_sats
    selected, total_in = [], 0

    # Seleção de UTXOs (greedy)
    for utxo in sorted(utxos, key=lambda u: u["value"], reverse=True):
        selected.append(utxo)
        total_in += utxo["value"]
        if total_in >= total_needed:
            break

    if total_in < total_needed:
        raise ValueError(
            f"Saldo insuficiente: disponível={total_in/COIN:.8f} PoLM, "
            f"necessário={total_needed/COIN:.8f} PoLM"
        )

    inputs = [{
        "txid":     u["txid"],
        "vout":     u["vout"],
        "sequence": 0xFFFFFFFF,
    } for u in selected]

    outputs = [{"value": amount_sats, "address": to_address}]

    change = total_in - total_needed
    if change > 546:  # dust limit
        outputs.append({"value": change, "address": from_address})

    tx = {
        "version":  1,
        "inputs":   inputs,
        "outputs":  outputs,
        "locktime": 0,
    }

    return wallet.sign(tx, from_address)

# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════

def _fmt_polm(sats: int) -> str:
    return f"{sats / COIN:.8f} PoLM"


def cmd_create(args) -> None:
    if os.path.exists(WALLET_FILE):
        print(f"⚠ Wallet já existe em {WALLET_FILE}")
        print("  Use 'backup' antes de criar uma nova.")
        return

    w = PoLMWallet.create_new()
    w.save()

    print("\n" + "═" * 60)
    print("  ✓ WALLET CRIADA COM SUCESSO")
    print("═" * 60)
    print(f"\n  Endereço principal:\n  {w.primary_address}")
    print(f"\n  Todos os endereços:")
    for addr in w.get_addresses():
        print(f"    {addr}")
    print(f"\n  ⚠  GUARDE ESTAS 24 PALAVRAS EM LUGAR SEGURO:")
    print(f"  ⚠  SEM ELAS VOCÊ PERDE SEUS PoLM PARA SEMPRE!\n")

    words = w.mnemonic.split()
    for i in range(0, len(words), 6):
        line = "  ".join(f"{i+j+1:2d}. {words[i+j]:<12}" for j in range(min(6, len(words)-i)))
        print(f"  {line}")

    print("\n" + "═" * 60 + "\n")
    print(f"  Wallet salva em: {WALLET_FILE}")
    print("  NUNCA compartilhe o arquivo wallet nem as palavras!\n")


def cmd_info(args) -> None:
    if not os.path.exists(WALLET_FILE):
        print("Wallet não encontrada. Execute: python3 polm_wallet.py create")
        return
    w = PoLMWallet.load()
    print(f"\n  Wallet: {w.label}")
    print(f"  Criada: {time.strftime('%Y-%m-%d %H:%M', time.localtime(w.created_at))}")
    print(f"\n  Endereços ({len(w.accounts)}):")
    for acc in w.accounts:
        print(f"    [{acc['index']}] {acc['address']}")
    print()


def cmd_balance(args) -> None:
    """Consulta saldo de um endereço conectando ao nó local."""
    addr = args.address
    if not addr:
        if not os.path.exists(WALLET_FILE):
            print("Wallet não encontrada.")
            return
        w    = PoLMWallet.load()
        addr = w.primary_address

    import urllib.request as _ur, json as _json
    try:
        data = _json.loads(_ur.urlopen(f"http://127.0.0.1:5556/balance?address={addr}").read())
        sats = data.get("balance_sats", 0)
        print(f"\n  Endereço : {addr}")
        print(f"  Saldo    : {sats / COIN:.8f} PoLM  ({sats} sats)\n")
    except Exception as e:
        print(f"Erro ao conectar ao nó: {e}")
        print("Certifique-se de que o nó está rodando (python3 polm_node.py)")


def cmd_send(args) -> None:
    """Envia PoLM para outro endereço via nó local."""
    if not os.path.exists(WALLET_FILE):
        print("Wallet não encontrada. Execute: python3 polm_wallet.py create")
        return

    w          = PoLMWallet.load()
    from_addr  = args.from_addr or w.primary_address
    to_addr    = args.to
    amount_sat = int(float(args.amount) * COIN)
    fee_sat    = int(float(args.fee) * COIN)

    if not validate_address(to_addr):
        print(f"Endereço destino inválido: {to_addr}")
        return

    # Busca UTXOs do nó local
    import urllib.request as _ur, json as _json
    try:
        data = _json.loads(_ur.urlopen(f"http://127.0.0.1:5556/utxos?address={from_addr}").read())
        utxos_raw = data.get("utxos", [])
        # Filtra UTXOs maduros
        import urllib.request as _ur3
        h = __import__("json").loads(_ur3.urlopen("http://127.0.0.1:5556/height").read())["height"]
        utxos = [u for u in utxos_raw if not u.get("coinbase") or (h - u["height"]) >= 100]
    except Exception as e:
        print(f"Erro ao conectar ao nó: {e}")
        return

    if not utxos:
        print(f"Sem UTXOs disponíveis em {from_addr}")
        print("(Lembre: coinbase leva 100 blocos para maturar)")
        return

    try:
        tx = build_tx(w, from_addr, to_addr, amount_sat, fee_sat, utxos)
    except ValueError as e:
        print(f"Erro: {e}")
        return

    # Envia tx ao nó
    try:
        import urllib.request as _ur2
        req  = _ur2.Request("http://127.0.0.1:5556/tx",
                           data=_json.dumps(tx).encode(),
                           headers={"Content-Type": "application/json"})
        data = _json.loads(_ur2.urlopen(req, timeout=5).read())
        if data.get("accepted"):
            print(f"\n  ✓ Transação enviada!")
            print(f"  TXID : {tx['txid']}")
            print(f"  Para : {to_addr}")
            print(f"  Valor: {amount_sat / COIN:.8f} PoLM")
            print(f"  Taxa : {fee_sat / COIN:.8f} PoLM\n")
        else:
            print(f"  ✗ Transação rejeitada: {data.get('reason', '?')}")
    except Exception as e:
        print(f"Erro ao enviar: {e}")


def cmd_receive(args) -> None:
    if not os.path.exists(WALLET_FILE):
        print("Wallet não encontrada.")
        return
    w = PoLMWallet.load()
    print(f"\n  Endereço para receber PoLM:")
    print(f"\n  {w.primary_address}\n")


def cmd_export(args) -> None:
    if not os.path.exists(WALLET_FILE):
        print("Wallet não encontrada.")
        return
    if not args.password:
        print("Uso: polm_wallet.py export --password SENHA")
        return
    w        = PoLMWallet.load()
    enc      = w.export_encrypted(args.password)
    out_file = "polm_wallet_backup.json"
    with open(out_file, "w") as f:
        json.dump(enc, f, indent=2)
    print(f"✓ Wallet exportada (criptografada) para: {out_file}")


def cmd_import(args) -> None:
    if not args.file:
        print("Uso: polm_wallet.py import --file polm_wallet_backup.json --password SENHA")
        return
    if not args.password:
        print("--password obrigatório para importar")
        return
    with open(args.file) as f:
        data = json.load(f)
    w = PoLMWallet.import_encrypted(data, args.password)
    w.save()
    print(f"✓ Wallet importada: {w.primary_address}")


def main():
    parser = argparse.ArgumentParser(
        description="PoLM Wallet — Carteira HD para a rede Proof of Legacy Memory"
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("create",  help="Cria nova wallet")
    sub.add_parser("info",    help="Informações da wallet")
    sub.add_parser("receive", help="Exibe endereço para receber")

    p_bal = sub.add_parser("balance", help="Consulta saldo")
    p_bal.add_argument("--address", default="", help="Endereço a consultar (padrão: wallet principal)")

    p_send = sub.add_parser("send", help="Envia PoLM")
    p_send.add_argument("--to",       required=True,  help="Endereço destino")
    p_send.add_argument("--amount",   required=True,  help="Quantidade em PoLM")
    p_send.add_argument("--fee",      default="0.001", help="Taxa em PoLM (padrão: 0.001)")
    p_send.add_argument("--from",     dest="from_addr", default="", help="Endereço origem")

    p_export = sub.add_parser("export", help="Exporta wallet criptografada")
    p_export.add_argument("--password", required=True)

    p_import = sub.add_parser("import", help="Importa wallet criptografada")
    p_import.add_argument("--file",     required=True)
    p_import.add_argument("--password", required=True)

    args = parser.parse_args()

    cmds = {
        "create":  cmd_create,
        "info":    cmd_info,
        "receive": cmd_receive,
        "balance": cmd_balance,
        "send":    cmd_send,
        "export":  cmd_export,
        "import":  cmd_import,
    }

    if args.cmd in cmds:
        cmds[args.cmd](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
