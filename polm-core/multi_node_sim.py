import hashlib
import time
import random
import threading

# -----------------------------
# Global Difficulty
# -----------------------------

TARGET_TIME = 20
WINDOW_SIZE = 5
TOLERANCE = 0.20

MAX_TARGET = 2**256 - 1
BASE_TARGET = 2**244

TARGET = BASE_TARGET

BASELINE_LATENCY = 0.30

difficulty_lock = threading.Lock()
interval_history = []
last_block_time = None
block_height = 0


class PoLMNode(threading.Thread):

    def __init__(self, name, latency, nonce_trials=100):
        super().__init__()
        self.name = name
        self.latency = latency
        self.nonce_trials = nonce_trials
        self.running = True

    def run(self):
        global TARGET, last_block_time, block_height

        while self.running:

            start = time.time()

            # Simula memory-bound latency
            time.sleep(self.latency)

            execution_time = time.time() - start

            # Latency weight
            latency_factor = execution_time / BASELINE_LATENCY
            latency_factor = min(max(latency_factor, 0.75), 1.35)

            effective_target = int(TARGET * latency_factor)

            base_data = f"{self.name}-{time.time()}"

            for nonce in range(self.nonce_trials):

                proof_input = f"{base_data}-{nonce}"
                proof_hash = hashlib.sha256(proof_input.encode()).hexdigest()
                hash_int = int(proof_hash, 16)

                if hash_int < effective_target:

                    with difficulty_lock:

                        now = time.time()
                        block_height += 1

                        print("\n=== BLOCK FOUND ===")
                        print("Winner:", self.name)
                        print("Block:", block_height)
                        print("Latency:", round(execution_time, 3))
                        print("Latency Factor:", round(latency_factor, 3))
                        print("Global Target:", TARGET)
                        print("Effective Target:", effective_target)
                        print("Hash:", proof_hash[:20], "...")

                        if last_block_time is not None:

                            interval = now - last_block_time
                            interval_history.append(interval)

                            if len(interval_history) > WINDOW_SIZE:
                                interval_history.pop(0)

                            avg_interval = sum(interval_history) / len(interval_history)

                            lower = TARGET_TIME * (1 - TOLERANCE)
                            upper = TARGET_TIME * (1 + TOLERANCE)

                            print("Avg Interval:", round(avg_interval, 2))

                            if avg_interval < lower:
                                TARGET = int(TARGET * 0.9)
                                print("Increasing difficulty")

                            elif avg_interval > upper:
                                TARGET = int(TARGET * 1.1)
                                if TARGET > MAX_TARGET:
                                    TARGET = MAX_TARGET
                                print("Decreasing difficulty")

                            print("New Global Target:", TARGET)

                        last_block_time = now
                        print("---------------------")

                    break


# -----------------------------
# Create Nodes
# -----------------------------

node_fast = PoLMNode("Node-A (Modern)", latency=0.24)
node_slow = PoLMNode("Node-B (Legacy)", latency=0.40)

print("=== PoLM Multi-Node Simulation v1.3 (Latency Weighted) ===")
print("Initial Target:", TARGET)

node_fast.start()
node_slow.start()
