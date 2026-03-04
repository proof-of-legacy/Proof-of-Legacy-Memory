from proof_logger import save_proof
import hashlib
import time
import platform
import json
import psutil
import random

# -----------------------------
# Config
# -----------------------------

TARGET_TIME = 30
WINDOW_SIZE = 5
TOLERANCE = 0.20

MAX_TARGET = 2**256 -1
TARGET = 2**244  # dificuldade inicial equilibrada

NONCE_TRIALS = 100  # tentativas por ciclo

RAM_GB = 1.0

# -----------------------------
# Load Identity
# -----------------------------

with open("node_id.json", "r") as f:
    identity = json.load(f)

NODE_ID = identity["node_id"]

# -----------------------------
# Memory Setup
# -----------------------------

total_ram = psutil.virtual_memory().total / (1024**3)
RAM_GB = min(RAM_GB, total_ram)

ram_bytes = int(RAM_GB * (1024**3))
buffer = bytearray(min(ram_bytes, 512 * 1024 * 1024))
buf_len = len(buffer)

node_info = platform.node()

last_proof_time = None
interval_history = []
proof_count = 0

print("=== PoLM Mining Started (Nonce Model v1.1) ===")
print("Initial Target:", TARGET)

# -----------------------------
# Mining Loop
# -----------------------------

while True:

    # -------- Memory Work (Latency-bound) --------
    start = time.time()

    ptr = 0
    rnd = random.Random(int(start))

    for _ in range(500000):

        i1 = (ptr + rnd.randint(1, 7919)) % buf_len
        i2 = (i1 + ptr) % buf_len

        v1 = buffer[i1]
        v2 = buffer[i2]

        mixed = (v1 * 31 + v2 * 17 + ptr) & 0xFF

        buffer[i1] = mixed
        buffer[i2] = (mixed ^ v1) & 0xFF

        ptr = (ptr + mixed) % buf_len

    execution_time = time.time() - start

    # Estado base derivado da memória
    memory_digest = hashlib.sha256(buffer[:1024]).hexdigest()
    base_data = f"{NODE_ID}-{memory_digest}-{execution_time}"

    # -------- Nonce Loop --------
    for nonce in range(NONCE_TRIALS):

        proof_input = f"{base_data}-{nonce}"
        proof_hash = hashlib.sha256(proof_input.encode()).hexdigest()
        hash_int = int(proof_hash, 16)

        if hash_int < TARGET:

            proof_count += 1
            now = time.time()

            save_proof(
                node_info,
                execution_time,
                proof_hash,
                NODE_ID
            )

            print("\n✔ VALID PROOF FOUND!")
            print("Proof #:", proof_count)
            print("Latency:", round(execution_time, 4))
            print("Nonce:", nonce)
            print("Hash:", proof_hash[:20], "...")
            print("Current Target:", TARGET)

            # -------- Difficulty Adjustment --------
            if last_proof_time is not None:

                interval = now - last_proof_time
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

                print("New Target:", TARGET)

            last_proof_time = now
            print("-----------------------------")

            break  # sai do nonce loop e volta para novo memory work
