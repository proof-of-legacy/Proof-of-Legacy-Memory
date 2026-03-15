"""
PoLM-X v2 — Wallet
ECDSA secp256k1 key generation, address derivation, transaction signing.
"""

import hashlib
import json
import os
import time
import secrets
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List

try:
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    print("[Wallet] WARNING: cryptography not installed — using mock keys")

from polm_x_core import Transaction, COIN_SYMBOL

# ─────────────────────────────────────────────
# ADDRESS GENERATION
# ─────────────────────────────────────────────
def pubkey_to_address(pubkey_hex: str) -> str:
    """
    Derive PoLM address from public key:
    POLM + first 32 chars of sha3_256(sha3_256(pubkey))
    """
    h1 = hashlib.sha3_256(bytes.fromhex(pubkey_hex)).hexdigest()
    h2 = hashlib.sha3_256(h1.encode()).hexdigest()
    return "POLM" + h2[:32].upper()

# ─────────────────────────────────────────────
# WALLET
# ─────────────────────────────────────────────
@dataclass
class WalletKey:
    private_key_hex: str
    public_key_hex:  str
    address:         str

class PoLMWallet:
    """
    HD-light wallet for PoLM-X.
    Generates ECDSA secp256k1 keypairs.
    """

    def __init__(self, wallet_file: str = "polmx_wallet.json"):
        self.wallet_file = wallet_file
        self.keys: Dict[str, WalletKey] = {}
        self._load_or_create()

    def _load_or_create(self):
        if os.path.exists(self.wallet_file):
            with open(self.wallet_file) as f:
                data = json.load(f)
            for addr, d in data.items():
                self.keys[addr] = WalletKey(**d)
            print(f"[Wallet] Loaded {len(self.keys)} address(es)")
        else:
            self.new_address(label="default")

    def _save(self):
        with open(self.wallet_file, "w") as f:
            json.dump({addr: asdict(k) for addr, k in self.keys.items()}, f, indent=2)

    def new_address(self, label: str = "") -> str:
        """Generate a new keypair and return the address."""
        if CRYPTO_AVAILABLE:
            priv = ec.generate_private_key(ec.SECP256K1(), default_backend())
            priv_hex = priv.private_bytes(
                serialization.Encoding.Raw,
                serialization.PrivateFormat.Raw,
                serialization.NoEncryption()
            ).hex()
            pub_hex = priv.public_key().public_bytes(
                serialization.Encoding.X962,
                serialization.PublicFormat.CompressedPoint
            ).hex()
        else:
            # Mock: random 32 bytes
            priv_hex = secrets.token_hex(32)
            pub_hex  = hashlib.sha3_256(bytes.fromhex(priv_hex)).hexdigest()

        address = pubkey_to_address(pub_hex)
        self.keys[address] = WalletKey(
            private_key_hex=priv_hex,
            public_key_hex=pub_hex,
            address=address
        )
        self._save()
        print(f"[Wallet] New address: {address}")
        return address

    def sign_tx(self, private_key_hex: str, message: bytes) -> str:
        """Sign message bytes, return hex signature."""
        if CRYPTO_AVAILABLE:
            from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
            priv = ec.derive_private_key(
                int(private_key_hex, 16), ec.SECP256K1(), default_backend()
            )
            sig = priv.sign(message, ec.ECDSA(hashes.SHA256()))
            return sig.hex()
        else:
            # Mock signature
            return hashlib.sha3_256(private_key_hex.encode() + message).hexdigest()

    def create_transaction(
        self,
        from_address: str,
        to_address: str,
        amount: float,
        fee: float = 0.001,
    ) -> Optional[Transaction]:
        if from_address not in self.keys:
            print(f"[Wallet] Address not in wallet: {from_address}")
            return None
        key = self.keys[from_address]
        timestamp = int(time.time())
        raw = f"{from_address}:{to_address}:{amount}:{fee}:{timestamp}".encode()
        signature = self.sign_tx(key.private_key_hex, raw)
        tx_id = hashlib.sha3_256(raw + signature.encode()).hexdigest()
        return Transaction(
            tx_id=tx_id,
            sender=from_address,
            receiver=to_address,
            amount=amount,
            fee=fee,
            timestamp=timestamp,
            signature=signature,
        )

    def addresses(self) -> List[str]:
        return list(self.keys.keys())

    def default_address(self) -> str:
        return list(self.keys.keys())[0]

    def show(self):
        print(f"\n[Wallet] {len(self.keys)} address(es):")
        for addr in self.keys:
            print(f"  {addr}")

# ─────────────────────────────────────────────
if __name__ == "__main__":
    w = PoLMWallet("/tmp/polmx_test_wallet.json")
    w.show()
    addr2 = w.new_address()
    tx = w.create_transaction(w.default_address(), addr2, 1.5)
    if tx:
        print(f"\n[Wallet] TX created: {tx.tx_id[:16]}…")
        print(f"  {tx.sender[:12]}… → {tx.receiver[:12]}…  {tx.amount} {COIN_SYMBOL}")
