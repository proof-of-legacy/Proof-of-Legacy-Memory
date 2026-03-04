import hashlib
import time
import threading

# ==========================================================
# CONFIGURAÇÕES GLOBAIS
# ==========================================================

TARGET = 2**244
BASELINE_LATENCY = 0.30
NONCE_TRIALS = 100

INITIAL_REWARD = 10
HALVING_INTERVAL = 50

# ==========================================================
# ESTRUTURA DO BLOCO
# ==========================================================

class Block:
    def __init__(self, index, timestamp, previous_hash,
                 winner, proof_hash, latency,
                 target, reward):

        self.index = index
        self.timestamp = timestamp
        self.previous_hash = previous_hash
        self.winner = winner
        self.proof_hash = proof_hash
        self.latency = latency
        self.target = target
        self.reward = reward
        self.hash = self.compute_hash()

    def compute_hash(self):
        block_string = (
            f"{self.index}"
            f"{self.timestamp}"
            f"{self.previous_hash}"
            f"{self.proof_hash}"
            f"{self.winner}"
            f"{self.reward}"
        )
        return hashlib.sha256(block_string.encode()).hexdigest()


# ==========================================================
# BLOCKCHAIN
# ==========================================================

class Blockchain:
    def __init__(self):
        self.chain = []
        self.ledger = {}
        self.create_genesis_block()

    def create_genesis_block(self):
        genesis = Block(
            index=0,
            timestamp=time.time(),
            previous_hash="0",
            winner="GENESIS",
            proof_hash="0",
            latency=0,
            target=0,
            reward=0
        )
        self.chain.append(genesis)

    def get_block_reward(self, height, latency_factor):
        halving_count = height // HALVING_INTERVAL
        base_reward = INITIAL_REWARD / (2 ** halving_count)

        # Bônus por latência (máx 20%)
        bonus = (latency_factor - 1) * 0.2
        bonus = min(max(bonus, 0), 0.2)

        final_reward = base_reward * (1 + bonus)
        return round(final_reward, 4)

    def add_block(self, winner, proof_hash,
                  latency, target, latency_factor):

        height = self.chain[-1].index + 1
        reward = self.get_block_reward(height, latency_factor)

        last_block = self.chain[-1]

        new_block = Block(
            index=height,
            timestamp=time.time(),
            previous_hash=last_block.hash,
            winner=winner,
            proof_hash=proof_hash,
            latency=latency,
            target=target,
            reward=reward
        )

        self.chain.append(new_block)

        if winner not in self.ledger:
            self.ledger[winner] = 0

        self.ledger[winner] += reward

        return new_block

    def is_valid(self):
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]

            if current.previous_hash != previous.hash:
                return False

            if current.hash != current.compute_hash():
                return False

        return True


# ==========================================================
# MINERADOR (NÓ)
# ==========================================================

blockchain = Blockchain()
lock = threading.Lock()


class PoLMNode(threading.Thread):

    def __init__(self, name, latency):
        super().__init__()
        self.name = name
        self.latency = latency
        self.running = True

    def run(self):
        global TARGET

        while self.running:

            start = time.time()
            time.sleep(self.latency)
            execution_time = time.time() - start

            latency_factor = execution_time / BASELINE_LATENCY
            latency_factor = min(max(latency_factor, 0.85), 1.25)

            effective_target = int(TARGET * latency_factor)

            base_data = f"{self.name}-{time.time()}"

            for nonce in range(NONCE_TRIALS):

                proof_input = f"{base_data}-{nonce}"
                proof_hash = hashlib.sha256(proof_input.encode()).hexdigest()
                hash_int = int(proof_hash, 16)

                if hash_int < effective_target:

                    with lock:

                        new_block = blockchain.add_block(
                            winner=self.name,
                            proof_hash=proof_hash,
                            latency=execution_time,
                            target=TARGET,
                            latency_factor=latency_factor
                        )

                        print("\n=== BLOCK ADDED ===")
                        print("Height:", new_block.index)
                        print("Winner:", self.name)
                        print("Reward:", new_block.reward)
                        print("Latency:", round(execution_time, 3))
                        print("Latency Factor:", round(latency_factor, 3))
                        print("Chain Valid:", blockchain.is_valid())
                        print("\n--- Ledger ---")

                        for node, balance in blockchain.ledger.items():
                            print(node, ":", round(balance, 4))

                        print("----------------------")

                    break


# ==========================================================
# EXECUÇÃO
# ==========================================================

node_fast = PoLMNode("Node-A (Modern)", latency=0.24)
node_slow = PoLMNode("Node-B (Legacy)", latency=0.40)

print("=== PoLM v1.6 Mini Blockchain + Halving + Latency Bonus ===")

node_fast.start()
node_slow.start()
