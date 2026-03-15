"""
polm_chain.py — Blockchain Storage & UTXO Engine
==================================================
Gerencia:
  • Armazenamento da cadeia em arquivo JSON comprimido
  • Índice UTXO (Unspent Transaction Outputs) como Bitcoin
  • Verificação de saldo por endereço
  • Validação completa de bloco + encadeamento
  • Retarget de dificuldade
  • Proteção contra double-spend
"""

import gzip
import json
import logging
import os
import threading
import time
from typing import Optional

from polm_core import (
    CHAIN_FILE, UTXO_FILE,
    MAX_SUPPLY_SATS, COINBASE_MATURITY, COIN,
    block_reward_sats, calculate_next_difficulty,
    hash_block_header, hash_transaction, merkle_root,
    validate_block_structure, validate_tx_structure,
    create_genesis_block, INITIAL_DIFFICULTY,
    hash_meets_target, _is_coinbase, MAX_REORG_DEPTH,
)

log = logging.getLogger("PoLM.Chain")

# ═══════════════════════════════════════════════════════════
# UTXO SET
# ═══════════════════════════════════════════════════════════

class UTXOSet:
    """
    Conjunto de saídas não gastas (Unspent Transaction Outputs).

    Estrutura interna:
        utxos[txid][vout] = {
            "value":   int (satoshis),
            "address": str,
            "height":  int (altura do bloco onde foi criado),
            "coinbase": bool,
        }
    """

    def __init__(self):
        self._utxos: dict[str, dict[int, dict]] = {}
        self._lock  = threading.RLock()

    # ── Consulta ─────────────────────────────────────────

    def get(self, txid: str, vout: int) -> Optional[dict]:
        return self._utxos.get(txid, {}).get(vout)

    def get_by_address(self, address: str, current_height: int) -> list[dict]:
        """Retorna todos os UTXOs de um endereço (excluindo imaturos)."""
        result = []
        with self._lock:
            for txid, outputs in self._utxos.items():
                for vout, utxo in outputs.items():
                    if utxo["address"] != address:
                        continue
                    # Coinbase imatura não pode ser gasta
                    if utxo.get("coinbase") and \
                       current_height - utxo["height"] < COINBASE_MATURITY:
                        continue
                    result.append({
                        "txid":  txid,
                        "vout":  vout,
                        "value": utxo["value"],
                        **utxo,
                    })
        return result

    def balance(self, address: str, current_height: int) -> int:
        """Retorna saldo em satoshis."""
        return sum(u["value"] for u in self.get_by_address(address, current_height))

    def exists(self, txid: str, vout: int) -> bool:
        return txid in self._utxos and vout in self._utxos[txid]

    # ── Modificação ──────────────────────────────────────

    def apply_block(self, block: dict) -> None:
        """Aplica todas as transações de um bloco ao UTXO set."""
        height    = block["height"]
        is_coinbase_block = True

        with self._lock:
            for tx in block["transactions"]:
                txid      = tx.get("txid") or hash_transaction(tx)
                is_coinbase_tx = _is_coinbase(tx)

                # Remove inputs gastos
                if not is_coinbase_tx:
                    for inp in tx["inputs"]:
                        inp_txid = inp["txid"]
                        inp_vout = inp["vout"]
                        if inp_txid in self._utxos and inp_vout in self._utxos[inp_txid]:
                            del self._utxos[inp_txid][inp_vout]
                            if not self._utxos[inp_txid]:
                                del self._utxos[inp_txid]

                # Adiciona outputs novos
                self._utxos.setdefault(txid, {})
                for i, out in enumerate(tx["outputs"]):
                    self._utxos[txid][i] = {
                        "value":   out["value"],
                        "address": out["address"],
                        "height":  height,
                        "coinbase": is_coinbase_tx,
                    }

                is_coinbase_block = False

    def revert_block(self, block: dict, prev_utxos: dict) -> None:
        """
        Reverte um bloco (para reorganização de cadeia).
        Requer snapshot do UTXO set antes do bloco ser aplicado.
        """
        with self._lock:
            for tx in block["transactions"]:
                txid = tx.get("txid") or hash_transaction(tx)
                # Remove outputs que foram criados por este bloco
                if txid in self._utxos:
                    del self._utxos[txid]
            # Restaura UTXOs gastos
            for txid, outputs in prev_utxos.items():
                self._utxos.setdefault(txid, {}).update(outputs)

    # ── Persistência ─────────────────────────────────────

    def save(self, path: str = UTXO_FILE) -> None:
        tmp  = path + ".tmp"
        data = {
            txid: {str(vout): utxo for vout, utxo in outputs.items()}
            for txid, outputs in self._utxos.items()
        }
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            json.dump(data, f, separators=(",", ":"))
        os.replace(tmp, path)

    def load(self, path: str = UTXO_FILE) -> None:
        if not os.path.exists(path):
            return
        try:
            with gzip.open(path, "rt", encoding="utf-8") as f:
                data = json.load(f)
            with self._lock:
                self._utxos = {
                    txid: {int(vout): utxo for vout, utxo in outputs.items()}
                    for txid, outputs in data.items()
                }
        except Exception as e:
            log.error("Erro ao carregar UTXO set: %s", e)

    def snapshot(self) -> dict:
        """Retorna cópia dos UTXOs (para rollback)."""
        with self._lock:
            return {
                txid: dict(outputs)
                for txid, outputs in self._utxos.items()
            }

    @property
    def total_supply_sats(self) -> int:
        """Calcula supply total atual (soma de todos os UTXOs)."""
        with self._lock:
            return sum(
                utxo["value"]
                for outputs in self._utxos.values()
                for utxo in outputs.values()
            )

# ═══════════════════════════════════════════════════════════
# BLOCKCHAIN
# ═══════════════════════════════════════════════════════════

class Blockchain:
    """
    Cadeia de blocos principal do PoLM.

    Responsabilidades:
      • Armazenar e indexar blocos
      • Validar blocos recebidos (estrutura + encadeamento + UTXO)
      • Manter UTXO set atualizado
      • Reorganização de cadeia (fork resolution)
      • Persistência em disco com escrita atômica
    """

    def __init__(self):
        self._chain:  list[dict] = []
        self._utxo   = UTXOSet()
        self._lock   = threading.RLock()
        self._height_index: dict[int, int] = {}   # height → chain index
        self._hash_index:   dict[str, int] = {}   # hash → chain index

    # ── Propriedades ─────────────────────────────────────

    @property
    def height(self) -> int:
        return len(self._chain) - 1

    @property
    def tip(self) -> Optional[dict]:
        return self._chain[-1] if self._chain else None

    @property
    def utxo(self) -> UTXOSet:
        return self._utxo

    # ── Inicialização ────────────────────────────────────

    def initialize(self) -> None:
        """Carrega ou cria a blockchain."""
        if os.path.exists(CHAIN_FILE):
            self._load()
            log.info("Blockchain carregada: %d blocos, altura=%d", len(self._chain), self.height)
        else:
            genesis = create_genesis_block()
            self._chain.append(genesis)
            self._update_indexes(genesis, 0)
            self._utxo.apply_block(genesis)
            self._save()
            log.info("Genesis block criado: %s", genesis["hash"][:16])

        # Carrega UTXO set (mais rápido que reprocessar a cadeia)
        if os.path.exists(UTXO_FILE):
            self._utxo.load()
        else:
            self._rebuild_utxo()

    # ── Adição de blocos ─────────────────────────────────

    def add_block(self, block: dict) -> tuple[bool, str]:
        """
        Valida e adiciona um bloco à cadeia.
        Thread-safe.
        """
        with self._lock:
            # 1. Validação estrutural
            ok, reason = validate_block_structure(block)
            if not ok:
                return False, f"estrutura: {reason}"

            # 2. Bloco já existe?
            if block["hash"] in self._hash_index:
                return False, "bloco duplicado"

            # 3. Encadeia com o tip atual?
            tip = self.tip
            if tip is None:
                return False, "cadeia vazia"

            if block["prev_hash"] != tip["hash"]:
                # Pode ser um fork — verifica se encadeia com bloco anterior
                parent_idx = self._hash_index.get(block["prev_hash"])
                if parent_idx is None:
                    return False, "prev_hash desconhecido"
                return self._handle_fork(block, parent_idx)

            # 4. Altura correta
            expected_height = tip["height"] + 1
            if block["height"] != expected_height:
                return False, f"altura incorreta: {block['height']} ≠ {expected_height}"

            # 5. Timestamp razoável
            if block["timestamp"] <= tip["timestamp"] - 7200:
                return False, "timestamp retroativo demais"

            # 6. Dificuldade correta
            expected_diff = calculate_next_difficulty(self._chain[-DIFFICULTY_WINDOW:])
            if abs(block["difficulty"] - expected_diff) > 2:
                return False, (
                    f"dificuldade incorreta: "
                    f"{block['difficulty']} ≠ {expected_diff} (±2)"
                )

            # 7. Valida transações contra UTXO set
            ok, reason = self._validate_block_txs(block)
            if not ok:
                return False, f"transações: {reason}"

            # 8. Aplica ao UTXO set e salva
            self._utxo.apply_block(block)
            self._chain.append(block)
            self._update_indexes(block, len(self._chain) - 1)
            self._save()
            self._utxo.save()

            return True, "ok"

    # ── Validação de transações ──────────────────────────

    def _validate_block_txs(self, block: dict) -> tuple[bool, str]:
        """
        Valida todas as transações do bloco contra o UTXO set atual.
        Verifica: double-spend, saldo suficiente, coinbase correta.
        """
        height   = block["height"]
        spent    = set()      # anti-double-spend dentro do bloco
        total_fees = 0

        for i, tx in enumerate(block["transactions"]):
            txid = tx.get("txid") or hash_transaction(tx)

            if _is_coinbase(tx):
                # Valida valor da coinbase
                expected_reward = block_reward_sats(height)
                total_out = sum(o["value"] for o in tx["outputs"])
                max_allowed = expected_reward + total_fees
                if total_out > max_allowed + 1:  # +1 para arredondamento
                    return False, (
                        f"coinbase excessiva: {total_out} > {max_allowed} "
                        f"(recompensa={expected_reward}, taxas={total_fees})"
                    )
                continue

            # TODO: verificacao ECDSA (reativar na v1.2)

            # Valida inputs
            total_in  = 0
            total_out = sum(o["value"] for o in tx["outputs"])

            for inp in tx["inputs"]:
                key = (inp["txid"], inp["vout"])
                if key in spent:
                    return False, f"tx {i}: double-spend dentro do bloco"
                spent.add(key)

                utxo = self._utxo.get(inp["txid"], inp["vout"])
                if utxo is None:
                    return False, f"tx {i}: UTXO {inp['txid'][:8]}:{inp['vout']} não existe"

                if utxo.get("coinbase") and height - utxo["height"] < COINBASE_MATURITY:
                    return False, f"tx {i}: coinbase imatura"

                total_in += utxo["value"]

            if total_in < total_out:
                return False, f"tx {i}: inputs ({total_in}) < outputs ({total_out})"

            total_fees += total_in - total_out

        return True, "ok"

    # ── Gestão de forks ──────────────────────────────────

    def _handle_fork(self, block: dict, parent_idx: int) -> tuple[bool, str]:
        """
        Resolve fork: aceita a cadeia mais longa (regra de Nakamoto).
        """
        # FIX: limita profundidade de reorganização
        reorg_depth = len(self._chain) - parent_idx - 1
        if reorg_depth > MAX_REORG_DEPTH:
            return False, f"reorg rejeitada: profundidade {reorg_depth} > {MAX_REORG_DEPTH}"

        fork_chain = self._chain[:parent_idx + 1] + [block]
        if len(fork_chain) <= len(self._chain):
            return False, "fork rejeitado: cadeia atual é mais longa"

        log.warning(
            "Fork detectado na altura %d — reorganizando cadeia "
            "(fork=%d blocos, local=%d blocos)",
            parent_idx, len(fork_chain), len(self._chain)
        )

        # Reconstrói UTXO a partir do ponto de divergência
        self._rebuild_utxo_from(fork_chain)
        self._chain = fork_chain
        self._rebuild_indexes()
        self._save()
        self._utxo.save()

        return True, "reorganização aceita"

    # ── Consultas ────────────────────────────────────────

    def get_block(self, height: int) -> Optional[dict]:
        idx = self._height_index.get(height)
        return self._chain[idx] if idx is not None else None

    def get_block_by_hash(self, h: str) -> Optional[dict]:
        idx = self._hash_index.get(h)
        return self._chain[idx] if idx is not None else None

    def get_recent_blocks(self, n: int = 10) -> list[dict]:
        return self._chain[-n:]

    def get_next_difficulty(self) -> int:
        window = self._chain[-DIFFICULTY_WINDOW:] if len(self._chain) >= 2 else self._chain
        return calculate_next_difficulty(window)

    def total_supply(self) -> int:
        return self._utxo.total_supply_sats

    # ── Indexes ──────────────────────────────────────────

    def _update_indexes(self, block: dict, idx: int) -> None:
        self._height_index[block["height"]] = idx
        self._hash_index[block["hash"]]     = idx

    def _rebuild_indexes(self) -> None:
        self._height_index = {}
        self._hash_index   = {}
        for i, b in enumerate(self._chain):
            self._update_indexes(b, i)

    # ── Persistência ─────────────────────────────────────

    def _save(self) -> None:
        tmp = CHAIN_FILE + ".tmp"
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            json.dump(self._chain, f, separators=(",", ":"))
        os.replace(tmp, CHAIN_FILE)

    def _load(self) -> None:
        try:
            with gzip.open(CHAIN_FILE, "rt", encoding="utf-8") as f:
                self._chain = json.load(f)
            self._rebuild_indexes()
        except Exception as e:
            log.critical("Erro ao carregar blockchain: %s — resetando.", e)
            self._chain = [create_genesis_block()]
            self._rebuild_indexes()
            self._save()

    def _rebuild_utxo(self) -> None:
        """Reconstrói o UTXO set do zero (varrendo toda a cadeia)."""
        log.info("Reconstruindo UTXO set (%d blocos)…", len(self._chain))
        self._utxo = UTXOSet()
        for block in self._chain:
            self._utxo.apply_block(block)
        self._utxo.save()
        log.info("UTXO set reconstruído.")

    def _rebuild_utxo_from(self, new_chain: list[dict]) -> None:
        self._utxo = UTXOSet()
        for block in new_chain:
            self._utxo.apply_block(block)


# Importação necessária para validate_block_structure
DIFFICULTY_WINDOW = 144
